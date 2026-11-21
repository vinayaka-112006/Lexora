"""Focused FastAPI contract tests; external generation is always mocked."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app import api  # noqa: E402


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str | None]] = []

    def retrieve(self, query: str, top_k: int, *, jurisdiction: str | None = None) -> list[dict]:
        self.calls.append((query, top_k, jurisdiction))
        return [{
            "chunk_id": "chunk-1", "text": "Section 3 excludes specified subject matter.",
            "document_name": "Patent Act", "filename": "patent_act.pdf", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "3", "provision_title": "Exclusions",
            "page_start": 1, "page_end": 2, "hybrid_score": 0.03,
            "dense_rank": 1, "bm25_rank": 1, "final_score": 0.04,
        }]


class FastAPIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_retriever_cache = api._retriever_cache
        api._retriever_cache = None
        self.client = TestClient(api.app)

    def tearDown(self) -> None:
        api._retriever_cache = self.previous_retriever_cache

    def test_health_is_ok_without_initializing_pipeline(self) -> None:
        with patch.object(api, "LegalRetriever") as retriever, patch.object(api, "OllamaClient") as llm:
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        retriever.assert_not_called()
        llm.assert_not_called()

    def test_valid_legal_query_returns_structured_response(self) -> None:
        fake_retriever = FakeRetriever()
        validation = {
            "valid": True, "total_citations": 1, "valid_citations": 1,
            "invalid_citations": 0, "citation_coverage": 1.0,
            "citations": [{"raw": "[Source: Patent Act, section 3, pp. 1-2]", "valid": True}],
        }
        confidence = {"score": 0.9, "decision": "answer", "reasons": []}
        claims = {"claim_count": 1, "uncertain_claims": 1, "claims": []}
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient", return_value=object()), \
             patch.object(api, "_generate_grounded_answer", return_value="Section 3 excludes matter. [Source: Patent Act, section 3, pp. 1-2]"), \
             patch.object(api, "validate_citations", return_value=validation), \
             patch.object(api, "verify_claims", return_value=claims), \
             patch.object(api, "score_confidence", return_value=confidence), \
             patch.object(api, "apply_confidence_decision", side_effect=lambda answer, _: answer):
            response = self.client.post("/query", json={
                "query": "What does Patent Act Section 3 say?",
            })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "What does Patent Act Section 3 say?")
        self.assertIn(body["decision"], {"answer", "answer_with_caution", "abstain", "generation_error"})
        self.assertIsInstance(body["answer"], str)
        self.assertIsInstance(body["citations"], list)
        self.assertIsInstance(body["sources"], list)
        self.assertIsInstance(body["retrieved_evidence"], list)
        self.assertEqual(fake_retriever.calls, [("What does Patent Act Section 3 say?", api.get_top_k(), None)])

    def test_unsupported_claim_is_displayed_with_caution(self) -> None:
        fake_retriever = FakeRetriever()
        validation = {
            "valid": True, "total_citations": 1, "valid_citations": 1,
            "invalid_citations": 0, "citation_coverage": 1.0, "citations": [],
        }
        claims = {
            "claim_count": 1, "unsupported_claims": 1, "uncertain_claims": 0,
            "claims": [{"claim_id": 1, "status": "unsupported", "text": "Unsupported legal claim."}],
        }
        confidence = {"score": 0.9, "decision": "answer", "reasons": []}
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient", return_value=object()), \
             patch.object(api, "_generate_grounded_answer", return_value="Unsupported legal claim."), \
             patch.object(api, "validate_citations", return_value=validation), \
             patch.object(api, "verify_claims", return_value=claims), \
             patch.object(api, "score_confidence", return_value=confidence):
            response = self.client.post("/query", json={"query": "What is a patent under Indian law?"})

        body = response.json()
        self.assertEqual(body["decision"], "answer_with_caution")
        self.assertTrue(body["answer"].startswith("Caution:"))
        self.assertEqual(body["claim_verification"]["claims"][0]["status"], "unsupported")

    def test_ayurvedic_follow_up_abstains_when_patentability_sources_are_absent(self) -> None:
        fake_retriever = FakeRetriever()
        irrelevant = {
            "chunk_id": "patent-2", "text": "An invention means a new product or process.",
            "document_id": "india:national/patent_act_2024",
            "document_name": "The Patents Act, 1970", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "2", "page_start": 8, "page_end": 10,
        }
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(FakeRetriever, "retrieve", return_value=[irrelevant]), \
             patch.object(api, "OllamaClient") as llm, \
             patch.object(api, "_generate_grounded_answer") as generate:
            response = self.client.post("/query", json={
                "query": "Follow-up request: How does this apply to Ayurvedic products? "
                         "Context: Patent Act; India jurisdiction; original topic: patent",
            })
        body = response.json()
        self.assertEqual(body["decision"], "abstain")
        self.assertIn("Patents Act provisions", body["abstention_reason"])
        self.assertIn("composition or process", body["answer"])
        llm.assert_not_called()
        generate.assert_not_called()

    def test_guard_abstention_preserves_evidence_and_skips_llm(self) -> None:
        fake_retriever = FakeRetriever()
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient") as llm, \
             patch.object(api, "_generate_grounded_answer") as generate, \
             self.assertLogs(api.logger, level="WARNING") as captured:
            response = self.client.post(
                "/query",
                headers={"X-Request-ID": "trace-fastapi-123"},
                json={"query": "What is the current patent filing fee?"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["decision"], "abstain")
        self.assertIn("freshness", body["abstention_reason"])
        self.assertEqual(body["citations"], [])
        self.assertEqual(len(body["retrieved_evidence"]), 1)
        llm.assert_not_called()
        generate.assert_not_called()
        self.assertEqual(response.headers["X-Request-ID"], "trace-fastapi-123")
        log_output = "\\n".join(captured.output)
        self.assertIn("RAG_REQUEST event=start request_id=trace-fastapi-123", log_output)
        self.assertIn("RAG_REQUEST event=complete request_id=trace-fastapi-123 http_status=200", log_output)
        self.assertIn(
            "RAG_STAGE_TIMING request_id=trace-fastapi-123 stage=query_endpoint_entered",
            log_output,
        )

    def test_retriever_is_initialized_once_and_reused_across_requests(self) -> None:
        fake_retriever = FakeRetriever()
        guard = SimpleNamespace(
            should_abstain=True,
            explanation="This test avoids generation.",
            category="test",
        )
        with patch.object(api, "LegalRetriever", return_value=fake_retriever) as constructor, \
             patch.object(api, "evaluate_abstention_guard", return_value=guard), \
             patch.object(api, "OllamaClient") as llm:
            responses = [
                self.client.post("/query", json={"query": "What does Section 3 say?"})
                for _ in range(2)
            ]

        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertTrue(all(response.json()["decision"] == "abstain" for response in responses))
        constructor.assert_called_once_with()
        self.assertEqual(len(fake_retriever.calls), 2)
        llm.assert_not_called()

    def test_missing_empty_and_whitespace_query_return_422(self) -> None:
        self.assertEqual(self.client.post("/query", json={}).status_code, 422)
        self.assertEqual(self.client.post("/query", json={"query": ""}).status_code, 422)
        self.assertEqual(self.client.post("/query", json={"query": "  \t  "}).status_code, 422)
        self.assertEqual(self.client.post("/query", content="{").status_code, 422)

    def test_groq_failure_diagnostics_use_groq_provider_model_and_key_redaction(self) -> None:
        fake_key = "fake-groq-key-for-redaction"
        failure = RuntimeError("Groq API request failed (HTTP 401)")
        failure.provider_status = 401
        failure.provider_error_type = "model_permission_error"
        failure.provider_error_code = "model_permission_blocked_project"
        failure.provider_error_reason = "authentication_failed"
        failure.provider_exception_class = "GroqAPIError"
        llm = SimpleNamespace(provider="groq", model="openai/gpt-oss-120b")
        with patch.dict("os.environ", {"GROQ_API_KEY": fake_key}, clear=True):
            with patch.object(api, "groq_key_configuration_diagnostics", return_value={
                "groq_api_key_present": True,
                "groq_api_key_matches_dotenv": False,
            }):
                diagnostics = api._generation_failure_diagnostics(failure, llm)
        self.assertEqual(diagnostics["provider"], "groq")
        self.assertEqual(diagnostics["model"], "openai/gpt-oss-120b")
        self.assertEqual(diagnostics["provider_status"], "401")
        self.assertEqual(diagnostics["provider_error_type"], "model_permission_error")
        self.assertEqual(diagnostics["provider_error_code"], "model_permission_blocked_project")
        self.assertTrue(diagnostics["groq_api_key_present"])
        self.assertFalse(diagnostics["groq_api_key_matches_dotenv"])
        self.assertNotIn(fake_key, repr(diagnostics))

    def test_groq_diagnostics_replace_unsafe_provider_identifiers(self) -> None:
        failure = RuntimeError("safe wrapper")
        failure.provider_error_type = "authorization=secret"
        failure.provider_error_code = "model permission blocked"
        failure.provider_error_reason = "permission_denied"
        llm = SimpleNamespace(provider="groq", model="openai/gpt-oss-120b")
        with patch.object(api, "groq_key_configuration_diagnostics", return_value={
            "groq_api_key_present": False,
            "groq_api_key_matches_dotenv": False,
        }):
            diagnostics = api._generation_failure_diagnostics(failure, llm)
        self.assertEqual(diagnostics["provider_error_type"], "unknown")
        self.assertEqual(diagnostics["provider_error_code"], "unknown")

    def test_gemini_failure_logs_safe_diagnostics_and_returns_generic_error(self) -> None:
        fake_retriever = FakeRetriever()
        fake_secret = "fake-gemini-secret-never-log"
        fake_authorization = "fake-bearer-credential-never-log"

        class FakeGeminiApiError(Exception):
            code = 503
            status = "UNAVAILABLE"
            response_json = {
                "error": {
                    "status": "UNAVAILABLE",
                    "code": 503,
                    "message": f"Sensitive provider body {fake_secret}; Authorization: Bearer {fake_authorization}",
                },
            }

            def __str__(self) -> str:
                return str(self.response_json)

        provider_error = FakeGeminiApiError()
        generate_content = Mock(side_effect=[provider_error, provider_error])
        gemini_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        google_module = ModuleType("google")
        google_module.genai = SimpleNamespace(
            Client=Mock(return_value=gemini_client),
            types=SimpleNamespace(HttpOptions=Mock(return_value=object())),
            errors=SimpleNamespace(APIError=FakeGeminiApiError),
        )
        messages = [{"role": "user", "content": "A private test prompt"}]

        with patch.dict(sys.modules, {"google": google_module}), \
             patch.dict("os.environ", {
                 "LLM_PROVIDER": "gemini",
                 "GEMINI_API_KEY": fake_secret,
                 "GEMINI_MODEL": "gemini-test-model",
             }), \
             patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "_generate_grounded_answer", side_effect=lambda _q, _chunks, llm: llm.generate(messages)), \
             self.assertLogs(api.logger, level="ERROR") as captured:
            response = self.client.post("/query", json={"query": "What does Patent Act Section 3 say?"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["decision"], "generation_error")
        self.assertIn("Answer generation failed. Please try again later.", body["answer"])
        self.assertNotIn(fake_secret, response.text)
        self.assertNotIn(fake_authorization, response.text)
        self.assertEqual(body["citations"], [])

        log_output = "\n".join(captured.output)
        self.assertIn('"provider":"gemini"', log_output)
        self.assertIn('"model":"gemini-test-model"', log_output)
        self.assertIn('"exception_class":"FakeGeminiApiError"', log_output)
        self.assertEqual(generate_content.call_count, 2)
        self.assertIn('"provider_status":"503"', log_output)
        self.assertIn('"provider_error_code":"UNAVAILABLE"', log_output)
        self.assertIn('"provider_error_reason":"provider_unavailable"', log_output)
        for sensitive_value in (fake_secret, fake_authorization, "Sensitive provider body", "A private test prompt"):
            self.assertNotIn(sensitive_value, log_output)

    def test_gemini_400_returns_generic_generation_error_without_retry_or_leak(self) -> None:
        fake_secret = "fake-invalid-argument-secret"

        class FakeGeminiClientError(Exception):
            code = 400
            status = "INVALID_ARGUMENT"
            message = fake_secret
            details = {"error": {"message": fake_secret}}

        generate_content = Mock(side_effect=FakeGeminiClientError())
        gemini_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        google_module = ModuleType("google")
        google_module.genai = SimpleNamespace(
            Client=Mock(return_value=gemini_client),
            types=SimpleNamespace(HttpOptions=Mock(return_value=object())),
            errors=SimpleNamespace(APIError=FakeGeminiClientError),
        )
        fake_retriever = FakeRetriever()

        with patch.dict(sys.modules, {"google": google_module}), \
             patch.dict("os.environ", {
                 "LLM_PROVIDER": "gemini",
                 "GEMINI_API_KEY": fake_secret,
                 "GEMINI_MODEL": "gemini-3.8-flash",
             }), \
             patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             self.assertLogs(api.logger, level="ERROR") as captured:
            response = self.client.post("/query", json={"query": "What does Section 3 say?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["decision"], "generation_error")
        self.assertEqual(
            response.json()["answer"].split("\n\n")[0],
            "Answer generation failed. Please try again later.",
        )
        self.assertEqual(generate_content.call_count, 1)
        self.assertIn('"provider_status":"400"', captured.output[0])
        self.assertIn('"provider_error_code":"INVALID_ARGUMENT"', captured.output[0])
        self.assertIn('"provider_error_reason":"invalid_request"', captured.output[0])
        self.assertNotIn(fake_secret, response.text)
        self.assertNotIn(fake_secret, "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
