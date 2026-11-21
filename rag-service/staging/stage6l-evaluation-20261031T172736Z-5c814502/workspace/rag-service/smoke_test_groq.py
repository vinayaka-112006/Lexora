"""One-shot Groq API smoke test; never logs credentials or raw API errors."""
from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import re

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)
API_HOST = "api.groq.com"
API_PATH = "/openai/v1/chat/completions"
TARGET_MODEL = "openai/gpt-oss-120b"
SAFE_FIELD_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
SAFE_ERROR_TYPES = {
    "invalid_request_error", "authentication_error", "rate_limit_error",
    "server_error", "model_permission_error",
}
SAFE_ERROR_CODES = {
    "invalid_api_key", "authentication_error", "invalid_request_error",
    "rate_limit_exceeded", "model_not_found", "context_length_exceeded",
    "server_error", "model_permission_blocked_org", "model_permission_blocked_project",
}


def _safe_field(value: object, secret: str | None = None) -> str:
    """Allow short identifiers only when they cannot reveal the configured key."""
    if (
        isinstance(value, str)
        and SAFE_FIELD_PATTERN.fullmatch(value)
        and not (secret and secret in value)
    ):
        return value
    return "unknown"


def safe_provider_error_fields(
    response: object, secret: str | None = None
) -> dict[str, str]:
    """Read a mocked/real HTTP error response and expose only safe type/code fields."""
    raw_status = getattr(response, "status", None)
    status = (
        str(raw_status)
        if isinstance(raw_status, int) and not isinstance(raw_status, bool)
        and 100 <= raw_status <= 599
        else "unknown"
    )
    try:
        body = response.read()  # type: ignore[attr-defined]
        parsed = json.loads(body.decode("utf-8"))
    except (AttributeError, OSError, http.client.HTTPException, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    error = parsed.get("error") if isinstance(parsed, dict) else None
    if not isinstance(error, dict):
        error = {}
    error_type = _safe_field(error.get("type"), secret)
    error_code = _safe_field(error.get("code"), secret)
    return {
        "http_status": status,
        "error_type": error_type if error_type in SAFE_ERROR_TYPES else "unknown",
        "error_code": error_code if error_code in SAFE_ERROR_CODES else "unknown",
    }


def key_configuration_status(
    project_root: Path = PROJECT_ROOT, effective_key: str | None = None
) -> dict[str, bool]:
    """Report key presence and dotenv parity without exposing either value."""
    if effective_key is None:
        effective_key = os.getenv("GROQ_API_KEY")
    dotenv_key = dotenv_values(project_root / ".env").get("GROQ_API_KEY")
    return {
        "groq_api_key_present": bool(effective_key),
        "groq_api_key_matches_dotenv": bool(
            effective_key and isinstance(dotenv_key, str) and effective_key == dotenv_key
        ),
    }


def _response_text(body: bytes) -> str | None:
    try:
        parsed = json.loads(body.decode("utf-8"))
        return parsed["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def main() -> None:
    model = os.getenv("GROQ_MODEL", TARGET_MODEL)
    api_key = os.getenv("GROQ_API_KEY")
    safe_model = (
        model if SAFE_FIELD_PATTERN.fullmatch(model) and not (api_key and api_key in model)
        else "unknown"
    )
    if os.getenv("LLM_PROVIDER", "").strip().lower() != "groq" or not api_key:
        print("request_succeeded=false")
        print("http_status=unknown")
        print(f"model={safe_model}")
        print("error.type=unknown")
        print("error.code=unknown")
        key_status = key_configuration_status(effective_key=api_key)
        print(f"groq_api_key_present={str(key_status['groq_api_key_present']).lower()}")
        print(f"groq_api_key_matches_dotenv={str(key_status['groq_api_key_matches_dotenv']).lower()}")
        return

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: GROQ_TEST_OK"}],
        "temperature": 0,
        "stream": False,
    }, separators=(",", ":"))
    connection = http.client.HTTPSConnection(API_HOST, timeout=15.0)
    try:
        # Exactly one POST call; there is no retry or redirect handling.
        connection.request(
            "POST",
            API_PATH,
            body=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        response = connection.getresponse()
        status = response.status
        if 200 <= status < 300:
            body = response.read()
            text = _response_text(body)
            if text is None:
                print("request_succeeded=false")
                print(f"http_status={status}")
                print(f"model={safe_model}")
                print("error=invalid_response")
                return
            if api_key in text:
                text = text.replace(api_key, "[REDACTED]")
            print("request_succeeded=true")
            print(f"http_status={status}")
            print(f"model={safe_model}")
            print(f"response={text}")
            key_status = key_configuration_status(effective_key=api_key)
            print(f"groq_api_key_present={str(key_status['groq_api_key_present']).lower()}")
            print(f"groq_api_key_matches_dotenv={str(key_status['groq_api_key_matches_dotenv']).lower()}")
            return

        fields = safe_provider_error_fields(response, api_key)
        print("request_succeeded=false")
        print(f"http_status={fields['http_status']}")
        print(f"model={safe_model}")
        print(f"error.type={fields['error_type']}")
        print(f"error.code={fields['error_code']}")
        key_status = key_configuration_status(effective_key=api_key)
        print(f"groq_api_key_present={str(key_status['groq_api_key_present']).lower()}")
        print(f"groq_api_key_matches_dotenv={str(key_status['groq_api_key_matches_dotenv']).lower()}")
    except (OSError, http.client.HTTPException, ValueError):
        print("request_succeeded=false")
        print("http_status=unknown")
        print(f"model={safe_model}")
        print("error.type=unknown")
        print("error.code=unknown")
        key_status = key_configuration_status(effective_key=api_key)
        print(f"groq_api_key_present={str(key_status['groq_api_key_present']).lower()}")
        print(f"groq_api_key_matches_dotenv={str(key_status['groq_api_key_matches_dotenv']).lower()}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
