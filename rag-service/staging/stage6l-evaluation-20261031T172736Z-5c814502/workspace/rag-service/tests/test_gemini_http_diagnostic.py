from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from diagnose_gemini_http_once import safe_error_fields  # noqa: E402


class GeminiHttpDiagnosticSanitizationTests(unittest.TestCase):
    def test_recognized_error_message_returns_only_fixed_label(self) -> None:
        secret = "AIzaFakeKey project-123 private prompt"
        result = safe_error_fields({"error": {
            "status": "INVALID_ARGUMENT",
            "message": "Invalid argument: " + secret,
            "details": {"private": secret},
        }})
        self.assertEqual(result, {
            "error_status": "INVALID_ARGUMENT",
            "provider_detail": "INVALID_REQUEST",
        })
        self.assertNotIn(secret, repr(result))
        self.assertNotIn("project-123", repr(result))
        self.assertNotIn("AIzaFakeKey", repr(result))

    def test_unknown_message_and_status_are_not_emitted(self) -> None:
        secret = "private project ID and request contents"
        result = safe_error_fields({"error": {
            "status": secret,
            "message": secret,
            "unknown_field": secret,
        }})
        self.assertEqual(result, {
            "error_status": "unknown",
            "provider_detail": "unavailable",
        })
        self.assertNotIn(secret, repr(result))

    def test_non_dictionary_error_is_unavailable(self) -> None:
        self.assertEqual(
            safe_error_fields({"error": "raw private response"}),
            {"error_status": "unknown", "provider_detail": "unavailable"},
        )


if __name__ == "__main__":
    unittest.main()
