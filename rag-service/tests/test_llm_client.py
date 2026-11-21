"""Configuration tests for the LLM provider selection."""
from __future__ import annotations

import os
import io
import json
import logging
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.llm_client import (  # noqa: E402
    IncompleteGenerationError, OllamaClient, _gemini_error_metadata, _groq_error_metadata,
    current_request_id, groq_key_configuration_diagnostics,
    reset_current_request_id, set_current_request_id,
)
from smoke_test_groq import key_configuration_status, safe_provider_error_fields  # noqa: E402


class LLMClientConfigurationTests(unittest.TestCase):
    def test_default_selects_ollama_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            client = OllamaClient()
        self.assertEqual(client.provider, "ollama")
        self.assertEqual(client.model, "llama3:latest")
        self.assertEqual(client.host, "http://localhost:11434")

    def test_ollama_generation_logs_request_id_duration_and_outcome(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"message":{"content":"Generated answer"}}'
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True), \
                patch("app.llm_client.urlopen", return_value=response), \
                self.assertLogs("app.llm_client", level="INFO") as captured:
            token = set_current_request_id("trace-ollama-123")
            try:
                self.assertEqual(
                    OllamaClient().generate([{"role": "user", "content": "private prompt"}]),
                    "Generated answer",
                )
            finally:
                reset_current_request_id(token)

        log_output = "\\n".join(captured.output)
        self.assertIn("event=start request_id=trace-ollama-123", log_output)
        self.assertIn("event=complete request_id=trace-ollama-123", log_output)
        self.assertIn("outcome=success", log_output)
        self.assertIn("duration_ms=", log_output)
        self.assertNotIn("private prompt", log_output)

    def test_ollama_generation_error_logs_same_id_without_error_text(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True), \
                patch("app.llm_client.urlopen", side_effect=TimeoutError("private endpoint detail")), \
                self.assertLogs("app.llm_client", level="INFO") as captured:
            token = set_current_request_id("trace-ollama-error")
            try:
                with self.assertRaisesRegex(RuntimeError, "Could not reach Ollama"):
                    OllamaClient().generate([{"role": "user", "content": "private prompt"}])
            finally:
                reset_current_request_id(token)

        log_output = "\\n".join(captured.output)
        self.assertIn("event=start request_id=trace-ollama-error", log_output)
        self.assertIn("event=error request_id=trace-ollama-error exception_class=RuntimeError", log_output)
        self.assertIn("event=complete request_id=trace-ollama-error", log_output)
        self.assertIn("outcome=error", log_output)
        self.assertNotIn("private endpoint detail", log_output)
        self.assertNotIn("private prompt", log_output)

    def test_ollama_generation_is_serialized_across_client_instances(self) -> None:
        active = 0
        maximum_active = 0
        active_guard = threading.Lock()

        def fake_generation(_messages):
            nonlocal active, maximum_active
            with active_guard:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.04)
            with active_guard:
                active -= 1
            return "Generated answer"

        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True), \
                patch.object(OllamaClient, "_perform_ollama_generation", side_effect=fake_generation):
            clients = [OllamaClient() for _ in range(3)]
            with ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(
                    lambda client: client.generate([{"role": "user", "content": "Question."}]),
                    clients,
                ))

        self.assertEqual(results, ["Generated answer"] * 3)
        self.assertEqual(maximum_active, 1)

    def test_ollama_request_keeps_settings_and_uses_128_token_limit(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"message":{"content":"Generated answer"}}'
        messages = [{"role": "user", "content": "Question."}]
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_MODEL": "llama3:latest",
            "OLLAMA_HOST": "http://127.0.0.1:11434",
        }, clear=True), patch("app.llm_client.urlopen", return_value=response) as urlopen_mock:
            result = OllamaClient().generate(messages)

        self.assertEqual(result, "Generated answer")
        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {
            "model": "llama3:latest",
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 768},
        })
        self.assertEqual(urlopen_mock.call_args.kwargs["timeout"], 240.0)

    def test_ollama_marks_length_terminated_text_as_incomplete(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            "message": {"content": "The statute provides that"},
            "done_reason": "length",
        }).encode()
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True), \
             patch("app.llm_client.urlopen", return_value=response):
            with self.assertRaises(IncompleteGenerationError) as raised:
                OllamaClient().generate([{"role": "user", "content": "Question."}])
        self.assertEqual(raised.exception.partial_text, "The statute provides that")
        self.assertEqual(raised.exception.metadata["done_reason"], "length")
        self.assertEqual(raised.exception.metadata["num_predict"], 768)

    def test_ollama_stop_terminated_text_remains_a_complete_response(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            "message": {"content": "The statute provides a rule."},
            "done_reason": "stop",
        }).encode()
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True), \
             patch("app.llm_client.urlopen", return_value=response):
            self.assertEqual(
                OllamaClient().generate([{"role": "user", "content": "Question."}]),
                "The statute provides a rule.",
            )

    def test_ollama_marks_done_false_as_incomplete_without_done_reason(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            "message": {"content": "The answer is cut off"}, "done": False,
        }).encode()
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True), \
             patch("app.llm_client.urlopen", return_value=response):
            with self.assertRaises(IncompleteGenerationError):
                OllamaClient().generate([{"role": "user", "content": "Question."}])

    def test_ollama_accepts_older_complete_response_without_completion_metadata(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"message":{"content":"Complete answer."}}'
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True), \
             patch("app.llm_client.urlopen", return_value=response):
            client = OllamaClient()
            self.assertEqual(client.generate([{"role": "user", "content": "Question."}]), "Complete answer.")
        self.assertIsNone(client.last_generation_metadata["done_reason"])
        self.assertEqual(client.last_generation_metadata["response_chars"], len("Complete answer."))

    def test_groq_403_model_permission_blocked_org_fields_are_safe(self) -> None:
        response = Mock()
        response.status = 403
        response.read.return_value = json.dumps({"error": {
            "type": "model_permission_error",
            "code": "model_permission_blocked_org",
            "message": "Sensitive response body and fake-key",
        }}).encode("utf-8")
        self.assertEqual(safe_provider_error_fields(response), {
            "http_status": "403",
            "error_type": "model_permission_error",
            "error_code": "model_permission_blocked_org",
        })

    def test_groq_403_model_permission_blocked_project_code_is_safe(self) -> None:
        response = Mock()
        response.status = 403
        response.read.return_value = json.dumps({"error": {
            "type": "model_permission_error",
            "code": "model_permission_blocked_project",
            "message": "Private project identifier and prompt",
        }}).encode("utf-8")
        self.assertEqual(safe_provider_error_fields(response), {
            "http_status": "403",
            "error_type": "model_permission_error",
            "error_code": "model_permission_blocked_project",
        })

    def test_groq_403_unknown_or_missing_code_is_unknown(self) -> None:
        for error_payload in (
            {"type": "model_permission_error", "code": "unrecognized code!", "message": "secret"},
            {"type": "model_permission_error", "message": "private details"},
        ):
            with self.subTest(error_payload=error_payload):
                response = Mock()
                response.status = 403
                response.read.return_value = json.dumps({"error": error_payload}).encode("utf-8")
                fields = safe_provider_error_fields(response)
                self.assertEqual(fields["http_status"], "403")
                self.assertEqual(fields["error_type"], "model_permission_error")
                self.assertEqual(fields["error_code"], "unknown")
                self.assertNotIn("secret", repr(fields))
                self.assertNotIn("private details", repr(fields))

    def test_groq_403_fields_matching_api_key_are_suppressed(self) -> None:
        secret = "fakekey_123456"
        response = Mock()
        response.status = 403
        response.read.return_value = json.dumps({"error": {
            "type": secret,
            "code": secret,
            "message": "not emitted",
        }}).encode("utf-8")
        self.assertEqual(safe_provider_error_fields(response, secret), {
            "http_status": "403",
            "error_type": "unknown",
            "error_code": "unknown",
        })

    def test_groq_structured_permission_codes_are_preserved_safely(self) -> None:
        for code in ("model_permission_blocked_org", "model_permission_blocked_project"):
            with self.subTest(code=code):
                body = json.dumps({"error": {
                    "type": "model_permission_error", "code": code,
                    "message": "private prompt and provider body",
                }}).encode()
                self.assertEqual(
                    _groq_error_metadata(403, body),
                    ("model_permission_error", code, "permission_denied"),
                )

    def test_groq_unknown_missing_and_unsafe_structured_fields_are_unknown(self) -> None:
        for error_payload in (
            {"type": "not a safe type", "code": "new-unknown-code"},
            {"type": "model_permission_error"},
            {"type": "authorization=secret", "code": "secret/value"},
        ):
            with self.subTest(error_payload=error_payload):
                body = json.dumps({"error": error_payload}).encode()
                error_type, error_code, _reason = _groq_error_metadata(403, body)
                if error_payload.get("type") == "model_permission_error":
                    self.assertEqual(error_type, "model_permission_error")
                else:
                    self.assertEqual(error_type, "unknown")
                self.assertEqual(error_code, "unknown")
                self.assertNotIn("secret", error_type + error_code)

    def test_groq_key_configuration_status_never_returns_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("GROQ_API_KEY=dotenv-secret-value\n", encoding="utf-8")
            self.assertEqual(
                key_configuration_status(root, "dotenv-secret-value"),
                {"groq_api_key_present": True, "groq_api_key_matches_dotenv": True},
            )
            self.assertEqual(
                key_configuration_status(root, "different-process-secret"),
                {"groq_api_key_present": True, "groq_api_key_matches_dotenv": False},
            )
            self.assertEqual(
                key_configuration_status(root, ""),
                {"groq_api_key_present": False, "groq_api_key_matches_dotenv": False},
            )

    def test_application_key_configuration_status_is_boolean_only(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": "effective-secret"}, clear=True), \
                patch("app.llm_client.dotenv_values", return_value={
                    "GROQ_API_KEY": "effective-secret",
                }):
            self.assertEqual(groq_key_configuration_diagnostics(), {
                "groq_api_key_present": True,
                "groq_api_key_matches_dotenv": True,
            })
        with patch.dict(os.environ, {"GROQ_API_KEY": "different-secret"}, clear=True), \
                patch("app.llm_client.dotenv_values", return_value={
                    "GROQ_API_KEY": "dotenv-secret",
                }):
            self.assertEqual(groq_key_configuration_diagnostics(), {
                "groq_api_key_present": True,
                "groq_api_key_matches_dotenv": False,
            })

    def test_groq_provider_uses_configured_model_and_key(self) -> None:
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "groq",
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_MODEL": "openai/gpt-oss-120b",
        }, clear=True):
            client = OllamaClient()
        self.assertEqual(client.provider, "groq")
        self.assertEqual(client.model, "openai/gpt-oss-120b")
        self.assertEqual(client.api_key, "test-groq-key")

    def test_groq_provider_requires_key_without_echoing_it(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY is required") as caught:
                OllamaClient()
        self.assertNotIn("test-groq-key", str(caught.exception))

    def test_groq_sends_messages_unchanged_and_parses_response(self) -> None:
        messages = [
            {"role": "system", "content": "Follow policy."},
            {"role": "user", "content": "Question."},
        ]
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read = Mock(return_value=b'{"choices":[{"message":{"content":" Answer "}}]}')
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "groq",
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_MODEL": "openai/gpt-oss-120b",
        }, clear=True), patch("app.llm_client.urlopen", return_value=response) as urlopen_mock:
            result = OllamaClient(temperature=0.0).generate(messages)

        self.assertEqual(result, "Answer")
        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-groq-key")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent, {
            "model": "openai/gpt-oss-120b",
            "messages": messages,
            "temperature": 0.0,
            "stream": False,
        })

    def test_groq_http_errors_are_sanitized(self) -> None:
        secret = "fake-groq-secret-never-leak"
        response_body = json.dumps({"error": {
            "code": "invalid_api_key",
            "message": "Sensitive provider response " + secret,
        }}).encode("utf-8")
        http_error = HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            io.BytesIO(response_body),
        )
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "groq", "GROQ_API_KEY": secret,
        }, clear=True), patch("app.llm_client.urlopen", side_effect=http_error):
            with self.assertRaises(RuntimeError) as caught:
                OllamaClient().generate([{"role": "user", "content": "Question."}])
        self.assertIn("HTTP 401", str(caught.exception))
        self.assertIn("authentication_failed", caught.exception.provider_error_reason)
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn("Sensitive provider response", str(caught.exception))
        self.assertEqual(caught.exception.provider_error_type, "unknown")
        self.assertEqual(caught.exception.provider_error_code, "invalid_api_key")

    def test_gemini_provider_uses_configured_model(self) -> None:
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-secret-do-not-print",
            "GEMINI_MODEL": "configured-test-model",
        }, clear=True):
            client = OllamaClient()
        self.assertEqual(client.provider, "gemini")
        self.assertEqual(client.model, "configured-test-model")
        self.assertTrue(client.api_key)

    def test_gemini_without_key_fails_without_echoing_key(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY is required") as caught:
                OllamaClient()
        self.assertNotIn("test-secret", str(caught.exception))

    def test_gemini_converts_messages_and_returns_text(self) -> None:
        messages = [
            {"role": "system", "content": "Follow the rules."},
            {"role": "user", "content": "Hello."},
            {"role": "assistant", "content": "Hi."},
            {"role": "user", "content": "Continue."},
        ]
        response = SimpleNamespace(text=" Generated answer ")
        class FakeAPIError(Exception):
            code = 503

        client_sdk = SimpleNamespace(
            models=SimpleNamespace(generate_content=Mock(return_value=response))
        )
        google_module = ModuleType("google")
        http_options = SimpleNamespace(HttpOptions=Mock(return_value="bounded-http-options"))
        google_module.genai = SimpleNamespace(
            Client=Mock(return_value=client_sdk),
            types=http_options,
            errors=SimpleNamespace(APIError=FakeAPIError),
        )
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-secret-do-not-print",
            "GEMINI_MODEL": "configured-test-model",
        }, clear=True), patch.dict(sys.modules, {"google": google_module}):
            client = OllamaClient(temperature=0.35)
            self.assertEqual(client.generate(messages), "Generated answer")

        google_module.genai.Client.assert_called_once_with(
            api_key="test-secret-do-not-print", http_options="bounded-http-options"
        )
        http_options.HttpOptions.assert_called_once_with(timeout=5000)
        client_sdk.models.generate_content.assert_called_once_with(
            model="configured-test-model",
            contents=[
                {"role": "user", "parts": [{"text": "Hello."}]},
                {"role": "model", "parts": [{"text": "Hi."}]},
                {"role": "user", "parts": [{"text": "Continue."}]},
            ],
            config={"temperature": 0.35, "system_instruction": "Follow the rules."},
        )

    def test_gemini_38_omits_unsupported_temperature_but_keeps_system_instruction(self) -> None:
        client_sdk = SimpleNamespace(
            models=SimpleNamespace(generate_content=Mock(return_value=SimpleNamespace(text="OK")))
        )
        google_module = ModuleType("google")
        google_module.genai = SimpleNamespace(
            Client=Mock(return_value=client_sdk),
            types=SimpleNamespace(HttpOptions=Mock(return_value=object())),
            errors=SimpleNamespace(APIError=type("FakeAPIError", (Exception,), {})),
        )
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-secret",
            "GEMINI_MODEL": "gemini-3.8-flash",
        }, clear=True), patch.dict(sys.modules, {"google": google_module}):
            self.assertEqual(
                OllamaClient(temperature=0.1).generate([
                    {"role": "system", "content": "System rule."},
                    {"role": "user", "content": "Question."},
                ]),
                "OK",
            )

        self.assertEqual(
            client_sdk.models.generate_content.call_args.kwargs["config"],
            {"system_instruction": "System rule."},
        )
        sent_contents = client_sdk.models.generate_content.call_args.kwargs["contents"]
        self.assertEqual(sent_contents[-1]["role"], "user")
        self.assertTrue(sent_contents[-1]["parts"][0]["text"].strip())
        self.assertTrue({"temperature", "top_p", "top_k", "candidate_count",
                         "frequency_penalty", "presence_penalty", "thinking_config"}.isdisjoint(
                             client_sdk.models.generate_content.call_args.kwargs["config"]
                         ))

    def test_gemini_retries_503_once_with_bounded_wait(self) -> None:
        class FakeAPIError(Exception):
            def __init__(self, code: int) -> None:
                self.code = code

        response = SimpleNamespace(text="OK")
        generate_content = Mock(side_effect=[FakeAPIError(503), response])
        client_sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        google_module = ModuleType("google")
        google_module.genai = SimpleNamespace(
            Client=Mock(return_value=client_sdk),
            types=SimpleNamespace(HttpOptions=Mock(return_value=object())),
            errors=SimpleNamespace(APIError=FakeAPIError),
        )
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test-secret",
        }, clear=True), patch.dict(sys.modules, {"google": google_module}), \
                patch("app.llm_client.time.sleep") as sleep:
            result = OllamaClient().generate([{"role": "user", "content": "OK"}])

        self.assertEqual(result, "OK")
        self.assertEqual(generate_content.call_count, 2)
        sleep.assert_called_once_with(0.2)

    def test_gemini_does_not_retry_non_503_api_error(self) -> None:
        class FakeAPIError(Exception):
            def __init__(self, code: int) -> None:
                self.code = code

        generate_content = Mock(side_effect=FakeAPIError(401))
        client_sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        google_module = ModuleType("google")
        google_module.genai = SimpleNamespace(
            Client=Mock(return_value=client_sdk),
            types=SimpleNamespace(HttpOptions=Mock(return_value=object())),
            errors=SimpleNamespace(APIError=FakeAPIError),
        )
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test-secret",
        }, clear=True), patch.dict(sys.modules, {"google": google_module}), \
                patch("app.llm_client.time.sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "Gemini API request failed"):
                OllamaClient().generate([{"role": "user", "content": "OK"}])

        self.assertEqual(generate_content.call_count, 1)
        sleep.assert_not_called()

    def test_gemini_400_api_error_is_not_retried(self) -> None:
        class FakeClientError(Exception):
            code = 400
            status = "INVALID_ARGUMENT"
            details = {"message": "sensitive provider body"}

        generate_content = Mock(side_effect=FakeClientError())
        client_sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        google_module = ModuleType("google")
        google_module.genai = SimpleNamespace(
            Client=Mock(return_value=client_sdk),
            types=SimpleNamespace(HttpOptions=Mock(return_value=object())),
            errors=SimpleNamespace(APIError=FakeClientError),
        )
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test-secret",
        }, clear=True), patch.dict(sys.modules, {"google": google_module}), \
                patch("app.llm_client.time.sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "Gemini API request failed") as caught:
                OllamaClient().generate([{"role": "user", "content": "Question."}])

        self.assertEqual(generate_content.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(caught.exception.provider_status, 400)
        self.assertEqual(caught.exception.provider_error_code, "INVALID_ARGUMENT")

    def test_gemini_client_error_metadata_is_safe_and_diagnostic(self) -> None:
        fake_sensitive_text = "private provider detail and fake-secret-value"

        class FakeClientError(Exception):
            code = 400
            status = "INVALID_ARGUMENT"
            message = fake_sensitive_text
            details = {"error": {"message": fake_sensitive_text}}
            response = fake_sensitive_text

        error = FakeClientError()
        self.assertEqual(
            _gemini_error_metadata(error), (400, "INVALID_ARGUMENT", "invalid_request")
        )

        client_sdk = SimpleNamespace(
            models=SimpleNamespace(generate_content=Mock(side_effect=error))
        )
        google_module = ModuleType("google")
        google_module.genai = SimpleNamespace(
            Client=Mock(return_value=client_sdk),
            types=SimpleNamespace(HttpOptions=Mock(return_value=object())),
            errors=SimpleNamespace(APIError=FakeClientError),
        )
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            with patch.dict(os.environ, {
                "LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key",
            }, clear=True), patch.dict(sys.modules, {"google": google_module}):
                with self.assertRaises(RuntimeError) as caught:
                    OllamaClient().generate([{"role": "user", "content": "private prompt"}])
        finally:
            root_logger.removeHandler(handler)

        self.assertEqual(str(caught.exception), "Gemini API request failed")
        self.assertEqual(caught.exception.provider_status, 400)
        self.assertEqual(caught.exception.provider_error_code, "INVALID_ARGUMENT")
        self.assertEqual(caught.exception.provider_error_reason, "invalid_request")
        self.assertNotIn(fake_sensitive_text, repr(_gemini_error_metadata(error)))
        self.assertNotIn(fake_sensitive_text, str(caught.exception))
        self.assertNotIn(fake_sensitive_text, log_stream.getvalue())

    def test_gemini_missing_or_malformed_provider_status_is_unknown(self) -> None:
        for provider_status in (
            None, "invalid argument", "INVALID-ARGUMENT", 400, "UNRECOGNIZED_SECRET_CODE"
        ):
            with self.subTest(provider_status=provider_status):
                error = Exception()
                error.code = 400
                error.status = provider_status
                self.assertEqual(_gemini_error_metadata(error), (400, "unknown", "unknown"))


if __name__ == "__main__":
    unittest.main()
