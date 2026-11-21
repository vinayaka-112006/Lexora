"""Focused tests for the deterministic pre-generation abstention guard."""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.abstention_guard import evaluate_abstention_guard  # noqa: E402
from app.confidence_scorer import score_confidence  # noqa: E402
from app import main as rag_main  # noqa: E402


class AbstentionGuardTests(unittest.TestCase):
    def test_required_clear_triggers(self) -> None:
        examples = {
            "What is the current official filing fee for a patent application submitted today in India?": "freshness",
            "What is the latest 2026 amendment to India's patent rules?": "freshness",
            "Has my company's trademark application been accepted by the Indian Trade Marks Registry?": "case_specific",
            "Which exact patent claims will be granted for my unpublished chemical formula?": "case_specific",
            "What damages would a U.S. court award for patent infringement under current federal law?": "unsupported_jurisdiction",
            "Is maple syrup from a particular Canadian region currently registered as a geographical indication?": "unsupported_jurisdiction",
            "Suggest a weekend meal plan using ingredients I already have at home.": "out_of_scope",
        }
        for query, expected_category in examples.items():
            with self.subTest(query=query):
                result = evaluate_abstention_guard(query)
                self.assertTrue(result.should_abstain)
                self.assertEqual(result.category, expected_category)
                self.assertTrue(result.explanation)

    def test_required_legal_queries_do_not_trigger(self) -> None:
        examples = [
            "What does Patent Act Section 3 say?",
            "What are the requirements under Trade Marks Act Section 34?",
            "What does Nagoya Protocol Article 6 require?",
            "What did the 2024 Patent Act provide in Section 3?",
            "What does Patent Act Section 3 say under Indian law?",
            "What does Nagoya Protocol Article 6 require under international law?",
        ]
        for query in examples:
            with self.subTest(query=query):
                self.assertFalse(evaluate_abstention_guard(query).should_abstain)

    def test_historical_latest_question_with_past_cutoff_is_allowed(self) -> None:
        result = evaluate_abstention_guard(
            "What was the latest amendment to India's Patent Rules as of 2020?"
        )
        self.assertFalse(result.should_abstain)

    def test_retrieved_text_does_not_override_guard(self) -> None:
        # The guard is intentionally query-driven; topical retrieved text cannot establish
        # current information or an individual application's status.
        current = evaluate_abstention_guard(
            "What is the latest 2026 amendment to India's patent rules?"
        )
        personal = evaluate_abstention_guard(
            "Has my company's trademark application been accepted?"
        )
        self.assertTrue(current.should_abstain)
        self.assertTrue(personal.should_abstain)

    def test_guard_trigger_skips_generation_and_confidence(self) -> None:
        events: list[str] = []

        class FakeRetriever:
            last_retrieval_debug = None

            def retrieve(self, query: str, top_k: int) -> list[dict]:
                events.append("retrieve")
                return [{"text": "Patent Act section text", "jurisdiction": "India"}]

        with patch.object(rag_main, "_print_retrieved_context"), \
             patch.object(rag_main, "_generate_grounded_answer") as generate, \
             patch.object(rag_main, "postprocess_generated_answer") as postprocess:
            with contextlib.redirect_stdout(io.StringIO()):
                rag_main._handle_question(
                    "What is the latest 2026 amendment to India's patent rules?",
                    FakeRetriever(), object(), 5,
                )
        self.assertEqual(events, ["retrieve"])
        generate.assert_not_called()
        postprocess.assert_not_called()

    def test_normal_legal_query_reaches_generation_before_existing_scorer(self) -> None:
        events: list[str] = []

        class FakeRetriever:
            last_retrieval_debug = None

            def retrieve(self, query: str, top_k: int) -> list[dict]:
                events.append("retrieve")
                return [{"chunk_id": "section-3", "text": "Section 3 excludes specified subject matter.",
                         "document_id": "india:national/patent_act", "document_name": "Patent Act",
                         "jurisdiction": "India", "provision_type": "section", "provision_number": "3",
                         "page_start": 1, "page_end": 2}]

        def generated(*args: object) -> str:
            events.append("generate")
            return "A generated answer."

        def postprocess(*args: object) -> dict:
            events.append("postprocess")
            return {
                "answer": "A generated answer.",
                "validation": {"valid": True, "total_citations": 0, "valid_citations": 0,
                               "invalid_citations": 0, "citation_coverage": 0.0, "citations": []},
                "confidence": {"score": 0.9, "level": "high", "decision": "answer", "reasons": []},
                "claim_verification": {"claims": [], "claim_count": 0, "citation_coverage": 0.0},
                "warnings": [],
            }

        with patch.object(rag_main, "_print_retrieved_context"), \
             patch.object(rag_main, "_generate_grounded_answer", side_effect=generated), \
             patch.object(rag_main, "postprocess_generated_answer", side_effect=postprocess), \
             patch.object(rag_main, "build_rag_result", return_value={"answer": "answer", "sources": []}), \
             patch.object(rag_main, "_print_citation_validation"), \
             patch.object(rag_main, "_print_confidence"), \
             patch.object(rag_main, "_print_claim_verification"):
            with contextlib.redirect_stdout(io.StringIO()):
                rag_main._handle_question("What does Patent Act Section 3 say?", FakeRetriever(), object(), 5)

        self.assertEqual(events, ["retrieve", "generate", "postprocess"])

    def test_existing_confidence_score_for_strong_exact_provision_is_unchanged(self) -> None:
        chunk = {
            "text": "Section 3 lists subject matter that is not an invention and is excluded from patentability.",
            "jurisdiction": "India", "provision_type": "section", "provision_number": "3",
            "provision_title": "What are not inventions",
        }
        citations = {"total_citations": 1, "valid_citations": 1,
                     "invalid_citations": 0, "citation_coverage": 1.0}
        result = score_confidence("What does Section 3 say under Indian law?", [chunk], citations)
        self.assertEqual((result["score"], result["decision"]), (1.0, "answer"))


if __name__ == "__main__":
    unittest.main()
