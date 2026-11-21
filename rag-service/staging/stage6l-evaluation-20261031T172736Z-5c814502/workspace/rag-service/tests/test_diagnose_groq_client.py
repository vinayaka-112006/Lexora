"""Offline output and call-contract tests for the Groq client diagnostic."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch
from urllib.error import HTTPError

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from diagnose_groq_client import (  # noqa: E402
    TEST_MESSAGE,
    format_failure,
    format_http_error,
    parse_error_body,
    run,
    safe_body_preview,
    safe_response_headers,
    sanitize_error_message,
)


class GroqClientDiagnosticTests(unittest.TestCase):
    def test_format_failure_outputs_only_status_and_sanitized_error_fields(self) -> None:
        output = format_failure(403, {
            "body_status": "structured_error",
            "error_message": "Model access denied.",
            "error_type": "model_permission_error",
            "error_code": "model_permission_blocked_project",
        })
        self.assertEqual(output.splitlines(), [
            "http_status=403",
            "body_status=structured_error",
            "error.message=Model access denied.",
            "error.type=model_permission_error",
            "error.code=model_permission_blocked_project",
        ])

    def test_failure_output_allows_known_structured_fields_only(self) -> None:
        secret = "fake-provider-message-and-key"
        output = format_failure(403, {
            "body_status": "structured_error",
            "error_message": "unavailable",
            "error_type": "model_permission_error",
            "error_code": "model_permission_blocked_project",
        })
        self.assertEqual(output.splitlines(), [
            "http_status=403",
            "body_status=structured_error",
            "error.message=unavailable",
            "error.type=model_permission_error",
            "error.code=model_permission_blocked_project",
        ])
        self.assertNotIn(secret, output)

    def test_missing_or_unsafe_fields_become_unknown(self) -> None:
        fields = parse_error_body(json.dumps({"error": {
            "message": "authorization: Bearer secret-value",
            "type": "Authorization: Bearer secret-value",
            "code": "private provider message",
        }}).encode())
        self.assertEqual(fields["body_status"], "missing_error_details")
        self.assertEqual(fields["error_type"], "unknown")
        self.assertEqual(fields["error_code"], "unknown")
        self.assertNotIn("secret-value", repr(fields))

    def test_run_makes_one_direct_request_with_app_configuration(self) -> None:
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = 200
        client = SimpleNamespace(
            provider="groq",
            model="openai/gpt-oss-120b",
            api_key="fake-secret",
            temperature=0.1,
            timeout=17,
        )
        stream = io.StringIO()
        with patch("diagnose_groq_client.urlopen", return_value=response) as request, \
                redirect_stdout(stream):
            result = run(client)
        self.assertEqual(result, 0)
        request.assert_called_once()
        self.assertEqual(request.call_args.kwargs["timeout"], 17)
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.full_url, "https://api.groq.com/openai/v1/chat/completions")
        sent_payload = json.loads(sent_request.data.decode())
        self.assertEqual(sent_payload, {
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": TEST_MESSAGE}],
            "temperature": 0.1,
            "stream": False,
        })
        self.assertEqual(stream.getvalue().splitlines(), [
            "http_status=200",
            "model=openai/gpt-oss-120b",
        ])
        self.assertNotIn("fake-secret", stream.getvalue())

    def test_structured_error_message_and_fields_are_extracted(self) -> None:
        body = json.dumps({"error": {
            "message": "You do not have access to this model.",
            "type": "model_permission_error",
            "code": "model_permission_blocked_org",
            "extra": "must not be displayed",
        }}).encode()
        self.assertEqual(parse_error_body(body), {
            "body_status": "structured_error",
            "error_message": "You do not have access to this model.",
            "error_type": "model_permission_error",
            "error_code": "model_permission_blocked_org",
        })

    def test_missing_fields_and_non_json_use_safe_fallbacks(self) -> None:
        self.assertEqual(parse_error_body(b"not json"), {
            "body_status": "malformed",
            "error_message": "unavailable",
            "error_type": "unknown",
            "error_code": "unknown",
        })
        self.assertEqual(parse_error_body(b'{"error":{"message":"","type":"bad","code":null}}'), {
            "body_status": "missing_error_details",
            "error_message": "unavailable",
            "error_type": "unknown",
            "error_code": "unknown",
        })

    def test_empty_body_is_reported_distinctly(self) -> None:
        self.assertEqual(parse_error_body(b""), {
            "body_status": "empty",
            "error_message": "unavailable",
            "error_type": "unknown",
            "error_code": "unknown",
        })

    def test_provider_message_redacts_credentials_and_secret_like_values(self) -> None:
        secret = "gsk_abcdefghijklmnopqrstuvwxyz123456"
        provider_message = (
            f"Authorization: Bearer {secret}\napi_key={secret}; "
            "secret=topsecret1234567890123456789012; general failure"
        )
        sanitized = sanitize_error_message(provider_message, api_key=secret)
        self.assertNotIn(secret, sanitized)
        self.assertNotIn("topsecret1234567890123456789012", sanitized)
        self.assertNotIn("Authorization:", sanitized)
        self.assertNotIn("Bearer", sanitized)
        self.assertIn("general failure", sanitized)

    def test_response_header_filter_allows_only_safe_metadata(self) -> None:
        secret = "gsk_fake_key_for_header_test"
        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Server": "cloudflare",
            "CF-Ray": "abc123-lhr",
            "X-Request-ID": "request-id-2",
            "Authorization": f"Bearer {secret}",
            "Set-Cookie": f"session={secret}",
            "X-Debug": "should-not-be-read",
        }
        self.assertEqual(safe_response_headers(headers, secret), {
            "content_type": "text/html; charset=utf-8",
            "server": "cloudflare",
            "request_id": "abc123-lhr",
        })

    def test_preview_redacts_secrets_or_omits_unsafe_content(self) -> None:
        key = "gsk_fake_key_for_preview_test"
        self.assertEqual(
            safe_body_preview(f"Access denied. Bearer {key}".encode(), key),
            "Access denied. [REDACTED]",
        )
        self.assertEqual(safe_body_preview(b"\xff\xfe"), "omitted")
        self.assertEqual(safe_body_preview(b"<html><body>Access denied</body></html>"), "omitted")

    def test_run_captures_only_fields_from_existing_http_error(self) -> None:
        secret = "gsk_fake_key_that_must_not_appear"
        body = json.dumps({"error": {
            "message": f"Authorization: Bearer {secret}\naccess_token={secret}; model access denied",
            "type": "model_permission_error",
            "code": "model_permission_blocked_project",
        }}).encode()
        http_error = HTTPError(
            "https://api.groq.com/openai/v1/chat/completions", 403,
            "Forbidden", {
                "Content-Type": "application/json",
                "Server": "cloudflare",
                "CF-Ray": "abc123-lhr",
                "Authorization": f"Bearer {secret}",
                "Set-Cookie": f"session={secret}",
            }, io.BytesIO(body),
        )
        stream = io.StringIO()
        client = SimpleNamespace(
            provider="groq", model="openai/gpt-oss-120b", api_key=secret,
            temperature=0.1, timeout=17,
        )
        with patch.dict("os.environ", {
            "LLM_PROVIDER": "groq", "GROQ_API_KEY": secret,
            "GROQ_MODEL": "openai/gpt-oss-120b",
        }, clear=True), patch("diagnose_groq_client.urlopen", side_effect=http_error) as request, \
                redirect_stdout(stream):
            result = run(client)

        output = stream.getvalue()
        self.assertEqual(result, 1)
        request.assert_called_once()
        self.assertIn("http_status=403", output)
        self.assertIn("error.type=model_permission_error", output)
        self.assertIn("error.code=model_permission_blocked_project", output)
        self.assertIn("body_status=structured_error", output)
        self.assertIn("content_type=application/json", output)
        self.assertIn("server=cloudflare", output)
        self.assertIn("request_id=abc123-lhr", output)
        self.assertIn(f"body_bytes={len(body)}", output)
        self.assertIn("preview=omitted", output)
        self.assertIn("model access denied", output)
        self.assertNotIn(secret, output)
        self.assertNotIn("Authorization:", output)
        self.assertNotIn("access_token", output)
        self.assertNotIn("Set-Cookie", output)
        self.assertNotIn(body.decode(), output)


if __name__ == "__main__":
    unittest.main()
