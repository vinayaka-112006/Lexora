from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from diagnose_gemini import (  # noqa: E402
    PROMPT,
    classify_provider_message,
    inspect_model_list,
    model_list_diagnostic,
    parse_diagnostic_arguments,
    parse_model_argument,
    perform_minimal_request,
    safe_api_version,
    safe_error_fields,
)


class GeminiDiagnosticTests(unittest.TestCase):
    def test_structured_error_reason_is_allowlisted_and_sensitive_fields_are_omitted(self) -> None:
        fake_key = "fake-api-key-never-print"
        fake_prompt = "private retrieved text and user prompt"
        error = Exception(f"{fake_key} {fake_prompt}")
        error.code = 400
        error.status = "INVALID_ARGUMENT"
        error.message = f"{fake_key} {fake_prompt}"
        error.details = {
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": error.message,
                "details": [{
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "SERVICE_DISABLED",
                    "domain": "googleapis.com",
                    "metadata": {
                        "service": "generativelanguage.googleapis.com",
                        "api_key": fake_key,
                        "prompt": fake_prompt,
                        "other": "must not be emitted",
                    },
                }],
            },
        }

        diagnostic = safe_error_fields(error)
        rendered = repr(diagnostic)
        self.assertEqual(diagnostic["http_status"], "400")
        self.assertEqual(diagnostic["provider_error_code"], "INVALID_ARGUMENT")
        self.assertEqual(diagnostic["provider_detail"], "SERVICE_DISABLED")
        self.assertEqual(diagnostic["provider_domain"], "googleapis.com")
        self.assertEqual(diagnostic["provider_service"], "generativelanguage.googleapis.com")
        for sensitive in (fake_key, fake_prompt, "must not be emitted", "message"):
            self.assertNotIn(sensitive, rendered)

    def test_unknown_error_info_and_arbitrary_metadata_are_unavailable(self) -> None:
        fake_secret = "credential-and-private-question"
        error = Exception(fake_secret)
        error.code = 400
        error.status = "INVALID_ARGUMENT"
        error.message = fake_secret
        error.details = {
            "error": {
                "status": "INVALID_ARGUMENT",
                "message": fake_secret,
                "details": [{
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "UNKNOWN_PRIVATE_REASON",
                    "domain": fake_secret,
                    "metadata": {"service": fake_secret, "other": fake_secret},
                }],
            },
        }

        diagnostic = safe_error_fields(error)
        self.assertEqual(diagnostic["provider_detail"], "unavailable")
        self.assertEqual(diagnostic["provider_domain"], "unavailable")
        self.assertEqual(diagnostic["provider_service"], "unavailable")
        self.assertNotIn(fake_secret, repr(diagnostic))

    def test_provider_message_is_reduced_to_a_fixed_label(self) -> None:
        fake_key = "AIza-fake-credential"
        fake_prompt = "private user question and retrieved text"
        error = Exception(f"model gemini-private-id not found; key={fake_key}; {fake_prompt}")
        error.code = 400
        error.status = "INVALID_ARGUMENT"
        error.message = str(error)
        error.details = {"error": {"details": [{
            "@type": "type.googleapis.com/google.rpc.ErrorInfo",
            "reason": "UNRECOGNIZED_REASON",
            "domain": "private-domain",
            "metadata": {"service": "private-service", "token": fake_key},
        }]}}

        diagnostic = safe_error_fields(error)
        self.assertEqual(diagnostic["provider_detail"], "MODEL_NOT_FOUND")
        for sensitive in (fake_key, fake_prompt, "gemini-private-id", "private-domain"):
            self.assertNotIn(sensitive, repr(diagnostic))

        self.assertEqual(
            classify_provider_message(f"invalid API key {fake_key}; {fake_prompt}"),
            "API_KEY_INVALID",
        )
        self.assertEqual(classify_provider_message("opaque provider text"), "unavailable")

    def test_sdk_message_fallback_classifies_known_reason_without_emitting_message(self) -> None:
        fake_sensitive = "project-123 private-prompt API_KEY=not-for-output"
        error = Exception("Invalid argument in request " + fake_sensitive)
        error.code = 400
        error.status = "INVALID_ARGUMENT"
        error.message = "Invalid argument in request " + fake_sensitive
        # This is the common SDK parsed shape when ErrorInfo details are absent.
        error.details = {"error": {
            "code": 400,
            "status": "INVALID_ARGUMENT",
            "message": error.message,
        }}

        diagnostic = safe_error_fields(error)
        self.assertEqual(diagnostic["provider_detail"], "INVALID_REQUEST")
        self.assertNotIn(fake_sensitive, repr(diagnostic))
        self.assertNotIn("project-123", repr(diagnostic))
        self.assertNotIn("not-for-output", repr(diagnostic))

    def test_sdk_message_fallback_keeps_unknown_message_unavailable(self) -> None:
        fake_sensitive = "project-456 private legal question"
        error = Exception(fake_sensitive)
        error.code = 400
        error.status = "INVALID_ARGUMENT"
        error.message = fake_sensitive
        error.details = {"error": {
            "code": 400,
            "status": "INVALID_ARGUMENT",
            "message": fake_sensitive,
        }}

        diagnostic = safe_error_fields(error)
        self.assertEqual(diagnostic["provider_detail"], "unavailable")
        self.assertNotIn(fake_sensitive, repr(diagnostic))
        self.assertNotIn("project-456", repr(diagnostic))

    def test_model_argument_defaults_to_gemini_3_8_flash(self) -> None:
        self.assertEqual(parse_model_argument([]), "gemini-3.8-flash")

    def test_model_argument_accepts_override(self) -> None:
        self.assertEqual(
            parse_model_argument(["--model", "gemini-2.5-flash"]),
            "gemini-2.5-flash",
        )

    def test_model_list_finds_target_model(self) -> None:
        found, supported = inspect_model_list([
            SimpleNamespace(name="models/gemini-3.8-flash", supported_actions=None)
        ])
        self.assertEqual(found, "true")
        self.assertEqual(supported, "unknown")

    def test_model_list_reports_target_absent(self) -> None:
        found, supported = inspect_model_list([
            SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=["generateContent"])
        ])
        self.assertEqual(found, "false")
        self.assertEqual(supported, "unknown")

    def test_model_list_reports_generate_content_support(self) -> None:
        found, supported = inspect_model_list([
            SimpleNamespace(name="models/gemini-3.8-flash", supported_actions=["generateContent"])
        ])
        self.assertEqual(found, "true")
        self.assertEqual(supported, "true")

    def test_model_list_unknown_methods_remain_unknown(self) -> None:
        found, supported = inspect_model_list([
            SimpleNamespace(name="models/gemini-3.8-flash")
        ])
        self.assertEqual(found, "true")
        self.assertEqual(supported, "unknown")

    def test_model_list_uses_sdk_list_method(self) -> None:
        models = Mock()
        models.list.return_value = [
            SimpleNamespace(name="models/gemini-3.8-flash", supported_actions=["generateContent"])
        ]
        self.assertEqual(model_list_diagnostic(SimpleNamespace(models=models)), ("true", "true"))
        models.list.assert_called_once_with()

    def test_list_mode_argument_does_not_change_smoke_default(self) -> None:
        args = parse_diagnostic_arguments(["--list-models"])
        self.assertTrue(args.list_models)
        self.assertEqual(args.model, "gemini-3.8-flash")

    def test_minimal_request_uses_only_model_and_plain_contents(self) -> None:
        generate_content = Mock(return_value=SimpleNamespace(text="OK"))
        client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

        perform_minimal_request(client, "gemini-3.8-flash")

        generate_content.assert_called_once_with(
            model="gemini-3.8-flash", contents="Reply with exactly: OK"
        )
        self.assertEqual(PROMPT, "Reply with exactly: OK")

    def test_installed_sdk_client_uses_expected_default_api_version(self) -> None:
        client = SimpleNamespace(
            _api_client=SimpleNamespace(
                _http_options=SimpleNamespace(api_version="v1beta")
            )
        )
        self.assertEqual(safe_api_version(client), "v1beta")


if __name__ == "__main__":
    unittest.main()
