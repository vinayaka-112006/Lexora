"""Focused FastAPI contract tests; external generation is always mocked."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from fastapi.testclient import TestClient

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app import api  # noqa: E402
from app.llm_client import IncompleteGenerationError  # noqa: E402


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

    def test_general_greeting_bypasses_retrieval_and_legal_verification(self) -> None:
        with patch.object(api, "_get_shared_retriever") as mock_retriever, \
             patch.object(api, "postprocess_generated_answer") as mock_postprocess:
            response = self.client.post("/query", json={"query": "hello"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "hello")
        self.assertEqual(body["decision"], "general")
        self.assertEqual(body["mode"], "general")
        self.assertEqual(body["answer"], "Hello! How can I help you today?")
        self.assertEqual(body["citations"], [])
        self.assertEqual(body["sources"], [])
        self.assertEqual(body["retrieved_evidence"], [])
        self.assertIsNone(body["abstention_reason"])
        self.assertIsNone(body["claim_verification"])
        self.assertIsNone(body["retrieval_diagnostic"])
        self.assertEqual(body["warnings"], [])
        # PROVE THAT RETRIEVAL AND LEGAL POSTPROCESSING WERE NEVER CALLED!
        mock_retriever.assert_not_called()
        mock_postprocess.assert_not_called()

    def test_general_creative_query_calls_direct_llm_without_retrieval(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Wishing you a wonderful birthday filled with joy and success!"
        with patch.object(api, "_get_shared_retriever") as mock_retriever, \
             patch.object(api, "postprocess_generated_answer") as mock_postprocess, \
             patch.object(api, "OllamaClient", return_value=mock_llm):
            response = self.client.post("/query", json={"query": "write a short birthday message"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["decision"], "general")
        self.assertEqual(body["mode"], "general")
        self.assertIn("birthday", body["answer"].lower())
        self.assertEqual(body["citations"], [])
        # PROVE THAT RETRIEVAL AND LEGAL POSTPROCESSING WERE NEVER CALLED!
        mock_retriever.assert_not_called()
        mock_postprocess.assert_not_called()
        mock_llm.generate.assert_called_once()

    def test_valid_legal_query_returns_structured_response(self) -> None:
        fake_retriever = FakeRetriever()
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient", return_value=SimpleNamespace(last_generation_metadata=None)), \
             patch.object(api, "_generate_grounded_answer", return_value="Section 3 excludes matter. [Source: Patent Act, section 3, pp. 1-2]"):
            response = self.client.post("/query", json={
                "query": "What does Patent Act Section 3 say?",
            })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "What does Patent Act Section 3 say?")
        self.assertIn(body["decision"], {"answer", "answer_with_caution", "abstain", "generation_error", "generation_incomplete"})
        self.assertIsInstance(body["answer"], str)
        self.assertIsInstance(body["citations"], list)
        self.assertIsInstance(body["sources"], list)
        self.assertIsInstance(body["retrieved_evidence"], list)
        self.assertEqual(fake_retriever.calls, [("What does Patent Act Section 3 say?", api.get_top_k(), None)])

    def test_uncited_claim_is_omitted_but_citation_matched_claim_is_preserved_with_caution(self) -> None:
        fake_retriever = FakeRetriever()
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient", return_value=object()), \
             patch.object(api, "_generate_grounded_answer", return_value=(
                 "Section 3 lists specified persons who need approval. "
                 "[Source: Patent Act, section 3, pp. 1-2]\n"
                 "Every Indian citizen needs that approval."
             )):
            response = self.client.post("/query", json={"query": "What is a patent under Indian law?"})

        body = response.json()
        self.assertEqual(body["decision"], "answer_with_caution")
        self.assertIn("Section 3 lists specified persons", body["answer"])
        self.assertNotIn("Every Indian citizen", body["answer"])
        self.assertIn("withheld", body["warnings"][0])
        self.assertEqual(body["claim_verification"]["withheld_claim_count"], 1)
        self.assertEqual(body["claim_verification"]["claims"][0]["status"], "uncertain")
        generated = body["claim_verification"]["generated_claims"]
        self.assertEqual(len(generated), 2)
        self.assertTrue(generated[0]["retained"])
        self.assertFalse(generated[1]["retained"])
        self.assertEqual(generated[1]["text"], "Every Indian citizen needs that approval.")
        self.assertIn("missing_citation", generated[1]["withheld_reasons"])
        self.assertIn("original_validation", body["claim_verification"])

    def test_debug_trace_is_opt_in_and_includes_query_and_retrieval_stages(self) -> None:
        fake_retriever = FakeRetriever()
        fake_retriever.last_retrieval_debug = {"retrieval_query": "normalized test query"}
        fake_retriever.last_retrieval_trace = {
            "dense_candidates": [{"chunk_id": "chunk-1", "rank": 1, "distance": 0.1}],
            "bm25_candidates": [{"chunk_id": "chunk-1", "rank": 2, "score": 1.2}],
            "final_results": [{"chunk_id": "chunk-1", "provision_number": "3"}],
        }
        with patch.dict("os.environ", {"RAG_DEBUG_TRACE": "1"}), \
             patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient", return_value=object()), \
             patch.object(api, "_generate_grounded_answer", side_effect=(
                 lambda _query, _chunks, _llm, diagnostics=None: (
                     diagnostics.update({"prompt_source_references": [{"source_id": "S1"}],
                                         "raw_llm_response": "Safe generated fixture."})
                     or "Safe generated fixture. [Source: Patent Act, section 3, pp. 1-2]"
                 )
             )):
            response = self.client.post("/query", json={"query": "What does Patent Act Section 3 say?"})

        diagnostics = response.json()["diagnostics"]
        self.assertEqual(diagnostics["original_question"], "What does Patent Act Section 3 say?")
        self.assertEqual(diagnostics["retrieval_debug"]["retrieval_query"], "normalized test query")
        self.assertEqual(diagnostics["retrieval_trace"]["dense_candidates"][0]["distance"], 0.1)
        self.assertEqual(diagnostics["prompt_source_references"][0]["source_id"], "S1")
        self.assertEqual(diagnostics["raw_llm_response"], "Safe generated fixture.")

    def test_coordinated_sections_expose_found_and_missing_diagnostic(self) -> None:
        fake_retriever = FakeRetriever()
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient") as llm:
            response = self.client.post("/query", json={
                "query": "Explain Sections 3 and 7 of the Biological Diversity Act, 2002.",
                "jurisdiction": "India",
            })
        body = response.json()
        self.assertEqual(body["decision"], "abstain")
        diagnostic = body["retrieval_diagnostic"]
        self.assertEqual([(item["number"], item["found"]) for item in diagnostic["requested"]],
                         [("3", True), ("7", False)])
        self.assertEqual([item["number"] for item in diagnostic["missing"]], ["7"])
        llm.assert_not_called()

    def test_incomplete_generation_is_returned_without_unverified_partial_text(self) -> None:
        fake_retriever = FakeRetriever()
        incomplete = IncompleteGenerationError("The statute provides that")
        incomplete.partial_answer = "The statute provides that [Source: Patent Act, section 3, pp. 1-2]"
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient", return_value=SimpleNamespace(provider="ollama", model="llama3:latest")), \
             patch.object(api, "_generate_grounded_answer", side_effect=incomplete):
            response = self.client.post("/query", json={"query": "What does Patent Act Section 3 say?"})
        body = response.json()
        self.assertEqual(body["decision"], "generation_incomplete")
        self.assertIn("incomplete and has not been verified", body["answer"])
        self.assertNotIn("The statute provides that", body["answer"])
        self.assertEqual(body["claim_verification"]["overall_status"], "not_evaluated_incomplete_generation")
        self.assertIn("withheld", body["warnings"][0])

    def test_citizenship_alone_is_not_reported_as_a_section7_exemption(self) -> None:
        fake_retriever = FakeRetriever()
        section7 = {
            "chunk_id": "bda-section-7", "text": "No person other than a person covered by section 3(2) shall access without prior intimation. Provided that this section shall not apply to cultivated medicinal plants. Section 7(2) requires a certificate of origin from the BMC.",
            "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "filename": "bda.pdf", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "provision_title": "Prior intimation",
            "page_start": 7, "page_end": 8,
        }
        with (
            patch.object(api, "LegalRetriever", return_value=fake_retriever),
            patch.object(FakeRetriever, "retrieve", return_value=[section7]),
            patch.object(api, "OllamaClient", return_value=object()),
            patch.object(api, "_generate_grounded_answer", return_value=(
                "As an Indian citizen, you are exempt from obtaining prior intimation to the State Biodiversity Board under section 7 for commercial use. [Source: Biological Diversity Act 2002, section 7, pp. 7-8]\n"
                "The cultivated medicinal plant exception requires a certificate of origin from the BMC. [Source: Biological Diversity Act 2002, section 7, pp. 7-8] [Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
            )),
        ):
            response = self.client.post("/query", json={
                "query": "I am an Indian citizen purchasing cultivated Ashwagandha roots for commercial use under Section 7.",
                "jurisdiction": "India",
            })
        body = response.json()
        self.assertEqual(body["decision"], "answer_with_caution")
        self.assertNotIn("you are exempt from obtaining prior intimation", body["answer"])
        self.assertIn("certificate of origin", body["answer"])
        self.assertIn("biodiversity claim was withheld", body["warnings"][1])
        self.assertEqual(body["answer"].count("[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"), 1)

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

    def test_missing_one_explicitly_requested_section_abstains_before_generation(self) -> None:
        fake_retriever = FakeRetriever()
        with patch.object(api, "LegalRetriever", return_value=fake_retriever), \
             patch.object(api, "OllamaClient") as llm, \
             patch.object(api, "_generate_grounded_answer") as generate:
            response = self.client.post("/query", json={
                "query": "Explain the difference between Section 3 and Section 7 of the Biological Diversity Act.",
                "jurisdiction": "India",
            })
        body = response.json()
        self.assertEqual(body["decision"], "abstain")
        self.assertIn("section 7", body["abstention_reason"].lower())
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
