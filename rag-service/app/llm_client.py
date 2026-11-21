"""Small client for Ollama and Google Gemini generation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
import logging
from contextvars import ContextVar
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values, load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
_PROJECT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
logger = logging.getLogger(__name__)
_request_id_context: ContextVar[str] = ContextVar("rag_request_id", default="unassigned")
_ollama_generation_lock = Lock()


class IncompleteGenerationError(RuntimeError):
    """Signal that a provider returned partial text after hitting its output limit."""

    def __init__(self, partial_text: str, metadata: dict[str, Any] | None = None):
        super().__init__("Generation stopped before the response was complete")
        self.partial_text = partial_text
        self.partial_answer = partial_text
        self.metadata = metadata or {}


def set_current_request_id(request_id: str) -> Any:
    """Set request-scoped correlation context and return its reset token."""
    return _request_id_context.set(request_id)


def reset_current_request_id(token: Any) -> None:
    _request_id_context.reset(token)


def current_request_id() -> str:
    return _request_id_context.get()


_GEMINI_ERROR_REASONS = {
    "INVALID_ARGUMENT": "invalid_request",
    "FAILED_PRECONDITION": "failed_precondition",
    "RESOURCE_EXHAUSTED": "resource_exhausted",
    "UNAVAILABLE": "provider_unavailable",
    "DEADLINE_EXCEEDED": "provider_deadline_exceeded",
    "UNAUTHENTICATED": "authentication_failed",
    "PERMISSION_DENIED": "permission_denied",
}


_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_STATUS_REASONS = {
    400: "invalid_request",
    401: "authentication_failed",
    403: "permission_denied",
    404: "resource_not_found",
    413: "request_too_large",
    429: "rate_limited",
    500: "provider_error",
    503: "provider_unavailable",
}
_GROQ_ERROR_CODE_REASONS = {
    "invalid_api_key": "authentication_failed",
    "authentication_error": "authentication_failed",
    "invalid_request_error": "invalid_request",
    "rate_limit_exceeded": "rate_limited",
    "model_not_found": "model_not_found",
    "context_length_exceeded": "request_too_large",
    "server_error": "provider_error",
    "model_permission_blocked_org": "permission_denied",
    "model_permission_blocked_project": "permission_denied",
}
_GROQ_SAFE_FIELD = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
_GROQ_ERROR_TYPES = frozenset({
    "invalid_request_error", "authentication_error", "rate_limit_error",
    "server_error", "model_permission_error",
})


def groq_key_configuration_diagnostics() -> dict[str, bool]:
    """Compare the effective key to root .env without returning either value."""
    effective_key = os.getenv("GROQ_API_KEY")
    env_key = dotenv_values(_PROJECT_ENV_PATH).get("GROQ_API_KEY")
    return {
        "groq_api_key_present": bool(effective_key),
        "groq_api_key_matches_dotenv": bool(
            effective_key and isinstance(env_key, str) and effective_key == env_key
        ),
    }


def _safe_groq_field(value: object) -> str:
    if isinstance(value, str) and _GROQ_SAFE_FIELD.fullmatch(value):
        return value
    return "unknown"


def _groq_error_metadata(http_status: int, response_body: bytes = b"") -> tuple[str, str, str]:
    """Return bounded structured identifiers and a coarse category only."""
    try:
        parsed = json.loads(response_body.decode("utf-8"))
        error = parsed.get("error") if isinstance(parsed, dict) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        error = None
    if not isinstance(error, dict):
        error = {}
    raw_type = _safe_groq_field(error.get("type"))
    raw_code = _safe_groq_field(error.get("code"))
    error_type = raw_type if raw_type in _GROQ_ERROR_TYPES else "unknown"
    error_code = raw_code if raw_code in _GROQ_ERROR_CODE_REASONS else "unknown"
    reason = _GROQ_ERROR_CODE_REASONS.get(
        error_code, _GROQ_STATUS_REASONS.get(http_status, "provider_error")
    )
    return error_type, error_code, reason


def _groq_error_reason(http_status: int, response_body: bytes = b"") -> str:
    """Return only an allowlisted Groq error category; never expose provider text."""
    return _groq_error_metadata(http_status, response_body)[2]


def _groq_runtime_error(
    message: str,
    *,
    http_status: int | None = None,
    reason: str = "unknown",
    error_type: str = "unknown",
    error_code: str = "unknown",
) -> RuntimeError:
    error = RuntimeError(message)
    error.provider_status = http_status
    error.provider_error_type = _safe_groq_field(error_type)
    error.provider_error_code = _safe_groq_field(error_code)
    error.provider_error_reason = reason
    error.provider_exception_class = "GroqAPIError"
    return error


def _gemini_error_metadata(error: Exception) -> tuple[int | None, str, str]:
    """Extract only bounded SDK status identifiers; never inspect raw error text."""
    http_status = getattr(error, "code", None)
    if not isinstance(http_status, int) or isinstance(http_status, bool):
        http_status = None

    provider_status = getattr(error, "status", None)
    if not isinstance(provider_status, str) or provider_status not in _GEMINI_ERROR_REASONS:
        provider_status = "unknown"
    safe_reason = _GEMINI_ERROR_REASONS.get(provider_status, "unknown")
    return http_status, provider_status, safe_reason


class OllamaClient:
    """Generate chat responses using Ollama, Gemini, or Groq."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        temperature: float = 0.1,
        timeout: float = 240.0,
    ) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
        if self.provider not in {"ollama", "gemini", "groq"}:
            raise ValueError("Unsupported LLM_PROVIDER. Choose 'ollama', 'gemini', or 'groq'.")
        model_variable, default_model = {
            "gemini": ("GEMINI_MODEL", "gemini-3.8-flash"),
            "groq": ("GROQ_MODEL", "openai/gpt-oss-120b"),
            "ollama": ("OLLAMA_MODEL", "llama3:latest"),
        }[self.provider]
        self.model = model or os.getenv(model_variable, default_model)
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.api_key = (
            os.getenv("GEMINI_API_KEY") if self.provider == "gemini"
            else os.getenv("GROQ_API_KEY") if self.provider == "groq"
            else None
        )
        self.temperature = temperature
        self.timeout = timeout
        self.last_generation_metadata: dict[str, Any] | None = None
        if self.provider == "gemini" and not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        if self.provider == "groq" and not self.api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq")

    def generate(self, messages: list[dict[str, str]]) -> str:
        """Send a non-streaming chat request and return its text response."""
        if self.provider == "gemini":
            return self._generate_gemini(messages)
        if self.provider == "groq":
            return self._generate_groq(messages)
        return self._generate_ollama(messages)

    def _generate_ollama(self, messages: list[dict[str, str]]) -> str:
        request_id = current_request_id()
        started_at = time.perf_counter()
        generation_started_at = None
        outcome = "error"
        logger.info("OLLAMA_GENERATION event=start request_id=%s", request_id)
        try:
            with _ollama_generation_lock:
                generation_started_at = time.perf_counter()
                logger.info(
                    "OLLAMA_GENERATION event=lock_acquired request_id=%s lock_wait_ms=%.3f",
                    request_id,
                    (generation_started_at - started_at) * 1000,
                )
                result = self._perform_ollama_generation(messages)
        except Exception as error:
            exception_class = type(error).__name__
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,79}", exception_class):
                exception_class = "unknown"
            logger.warning(
                "OLLAMA_GENERATION event=error request_id=%s exception_class=%s",
                request_id,
                exception_class,
            )
            raise
        else:
            outcome = "success"
            return result
        finally:
            logger.info(
                "OLLAMA_GENERATION event=complete request_id=%s duration_ms=%.3f "
                "generation_ms=%.3f outcome=%s",
                request_id,
                (time.perf_counter() - started_at) * 1000,
                (time.perf_counter() - generation_started_at) * 1000
                if generation_started_at is not None else 0.0,
                outcome,
            )

    def _perform_ollama_generation(self, messages: list[dict[str, str]]) -> str:
        num_predict = 768
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": 8192, "num_predict": num_predict},
        }
        request = Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Ollama request failed (HTTP {error.code}). Ensure Ollama is running and "
                f"model {self.model!r} is available. Details: {details}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise RuntimeError(
                f"Could not reach Ollama at {self.host}. Start the Ollama service and ensure "
                f"model {self.model!r} is available (for example, run 'ollama pull {self.model}'). "
                f"Details: {error}"
            ) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RuntimeError(f"Ollama returned an invalid response: {error}") from error

        if result.get("error"):
            raise RuntimeError(
                f"Ollama could not use model {self.model!r}: {result['error']}. "
                f"Ensure the model is available with 'ollama pull {self.model}'."
            )
        content = (result.get("message") or {}).get("content")
        done_reason = result.get("done_reason")
        if not isinstance(done_reason, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", done_reason):
            done_reason = None
        prompt_eval_count = result.get("prompt_eval_count")
        eval_count = result.get("eval_count")
        self.last_generation_metadata = {
            "done_reason": done_reason,
            "done": result.get("done") if isinstance(result.get("done"), bool) else None,
            "prompt_eval_count": prompt_eval_count if isinstance(prompt_eval_count, int) else None,
            "eval_count": eval_count if isinstance(eval_count, int) else None,
            "num_predict": num_predict,
            "response_chars": len(content) if isinstance(content, str) else 0,
        }
        logger.info(
            "OLLAMA_GENERATION_METADATA request_id=%s done_reason=%s done=%s "
            "prompt_eval_count=%s eval_count=%s num_predict=%s response_chars=%s",
            current_request_id(), done_reason or "unknown", self.last_generation_metadata["done"],
            self.last_generation_metadata["prompt_eval_count"],
            self.last_generation_metadata["eval_count"], num_predict,
            self.last_generation_metadata["response_chars"],
        )
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned an empty answer")
        if done_reason in {"length", "max_tokens"} or result.get("done") is False:
            raise IncompleteGenerationError(content.strip(), self.last_generation_metadata)
        return content.strip()

    def _generate_groq(self, messages: list[dict[str, str]]) -> str:
        """Send the existing messages unchanged to the OpenAI-compatible Groq API."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": False,
        }
        request = Request(
            _GROQ_API_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                self.last_http_status = getattr(response, "status", None)
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                body = error.read()
            except OSError:
                body = b""
            error_type, error_code, reason = _groq_error_metadata(error.code, body)
            raise _groq_runtime_error(
                f"Groq API request failed (HTTP {error.code})",
                http_status=error.code,
                reason=reason,
                error_type=error_type,
                error_code=error_code,
            ) from None
        except (URLError, TimeoutError, OSError):
            raise _groq_runtime_error(
                "Could not reach Groq API (network or timeout error).",
                reason="network_error",
            ) from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise _groq_runtime_error(
                "Groq API returned an invalid response.", reason="invalid_response"
            ) from None

        if isinstance(result, dict) and result.get("error"):
            error_type, error_code, reason = _groq_error_metadata(
                200, json.dumps(result).encode("utf-8")
            )
            raise _groq_runtime_error(
                "Groq API returned an error response.", reason=reason,
                error_type=error_type, error_code=error_code,
            )
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            content = None
        if not isinstance(content, str) or not content.strip():
            raise _groq_runtime_error(
                "Groq API response did not contain generated text.",
                reason="missing_model_response",
            )
        return content.strip()

    def _generate_gemini(self, messages: list[dict[str, str]]) -> str:
        """Convert chat messages to Gemini contents and return generated text."""
        from google import genai

        system_instructions = []
        contents = []
        for message in messages:
            role = message.get("role", "user")
            text = message.get("content", "")
            if role == "system":
                system_instructions.append(text)
                continue
            if role == "assistant":
                role = "model"
            elif role not in {"user", "model"}:
                raise RuntimeError(f"Unsupported Gemini message role: {role}")
            contents.append({"role": role, "parts": [{"text": text}]})

        config: dict[str, Any] = {}
        model_name = self.model.rsplit("/", 1)[-1]
        model_version = re.match(r"^gemini-(\d+)\.(\d+)-", model_name)
        # Gemini 3.6 and later reject deprecated sampling parameters such as
        # temperature. Earlier Gemini models continue to receive the configured value.
        if not model_version or tuple(map(int, model_version.groups())) < (3, 6):
            config["temperature"] = self.temperature
        if system_instructions:
            config["system_instruction"] = "\n\n".join(system_instructions)
        try:
            # A 5 second per-attempt limit and 0.2 second wait keep two attempts
            # comfortably inside the Node proxy's existing 15 second deadline.
            client = genai.Client(
                api_key=self.api_key,
                http_options=genai.types.HttpOptions(timeout=5000),
            )
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )
                    break
                except genai.errors.APIError as error:
                    if attempt == 0 and error.code == 503:
                        time.sleep(0.2)
                        continue
                    raise
        except Exception as error:
            wrapped_error = RuntimeError("Gemini API request failed")
            (wrapped_error.provider_status,
             wrapped_error.provider_error_code,
             wrapped_error.provider_error_reason) = (
                _gemini_error_metadata(error)
            )
            wrapped_error.provider_exception_class = type(error).__name__
            raise wrapped_error from None

        content = getattr(response, "text", None)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Gemini API response did not contain generated text")
        return content.strip()
