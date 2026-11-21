"""Deterministic confidence scorer tests independent of retrieval and Ollama services."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.confidence_scorer import (  # noqa: E402
    ABSTENTION_MESSAGE,
    apply_confidence_decision,
    score_confidence,
)


class ConfidenceScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.section3 = {
            "chunk_id": "patent-3",
            "text": "Section 3 lists subject matter that is not an invention and is excluded from patentability.",
            "document_name": "Patents Act 2024",
            "jurisdiction": "India",
            "provision_type": "section",
            "provision_number": "3",
            "provision_title": "What are not inventions",
            "page_start": 11,
            "page_end": 12,
        }
        self.valid_citations = {
            "valid": True,
            "total_citations": 1,
            "valid_citations": 1,
            "invalid_citations": 0,
            "citation_coverage": 1.0,
        }

    def test_strong_evidence_and_valid_citation_is_high(self) -> None:
        result = score_confidence("What does Section 3 say under Indian law?", [self.section3], self.valid_citations)
        self.assertEqual((result["level"], result["decision"]), ("high", "answer"))
        self.assertGreaterEqual(result["score"], 0.75)

    def test_explicit_retrieved_provision_increases_confidence(self) -> None:
        normal = score_confidence("Tell me about this provision under Indian law.", [self.section3], self.valid_citations)
        explicit = score_confidence("What does Section 3 say under Indian law?", [self.section3], self.valid_citations)
        self.assertGreater(explicit["score"], normal["score"])

    def test_missing_explicit_provision_abstains(self) -> None:
        result = score_confidence("What does Section 4 say under Indian law?", [self.section3], self.valid_citations)
        self.assertEqual((result["level"], result["decision"]), ("low", "abstain"))
        self.assertLessEqual(result["score"], 0.44)

    def test_wrong_jurisdiction_reduces_score(self) -> None:
        international = dict(self.section3, jurisdiction="International")
        correct = score_confidence("What is excluded under Indian law?", [self.section3], self.valid_citations)
        wrong = score_confidence("What is excluded under Indian law?", [international], self.valid_citations)
        self.assertLess(wrong["score"], correct["score"])
        self.assertIn("jurisdiction_mismatch", wrong["adjustments"])

    def test_high_citation_coverage_increases_confidence(self) -> None:
        no_citations = {"total_citations": 0, "valid_citations": 0, "invalid_citations": 0, "citation_coverage": 0.0}
        result_without = score_confidence("What is excluded?", [self.section3], no_citations)
        result_with = score_confidence("What is excluded?", [self.section3], self.valid_citations)
        self.assertGreater(result_with["score"], result_without["score"])

    def test_zero_citations_reduce_confidence(self) -> None:
        no_citations = {"total_citations": 0, "valid_citations": 0, "invalid_citations": 0, "citation_coverage": 0.0}
        result = score_confidence("What is excluded?", [self.section3], no_citations)
        self.assertEqual(result["adjustments"]["no_citations"], -15.0)

    def test_no_retrieved_evidence_abstains(self) -> None:
        result = score_confidence("What is excluded?", [], self.valid_citations)
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["decision"], "abstain")

    def test_comparison_rewards_both_jurisdictions(self) -> None:
        international = {
            "chunk_id": "nagoya-2", "text": "Access to genetic resources and benefit-sharing.",
            "document_name": "Nagoya Protocol", "jurisdiction": "International",
            "provision_type": "article", "provision_number": "2",
            "page_start": 5, "page_end": 6,
        }
        question = "Compare Indian law with the Nagoya Protocol rules."
        both = score_confidence(question, [self.section3, international], self.valid_citations)
        one = score_confidence(question, [self.section3], self.valid_citations)
        self.assertGreater(both["score"], one["score"])
        self.assertIn("Retrieved evidence covers both requested jurisdictions.", both["reasons"])

    def test_repeated_input_is_deterministic(self) -> None:
        question = "What does Section 3 say under Indian law?"
        first = score_confidence(question, [self.section3], self.valid_citations)
        second = score_confidence(question, [self.section3], self.valid_citations)
        self.assertEqual(first, second)

    def test_medium_confidence_uses_caution(self) -> None:
        chunks = [dict(self.section3, text="") for _ in range(4)] + [dict(self.section3, provision_number="99")]
        citation_data = {
            "total_citations": 2, "valid_citations": 1, "invalid_citations": 1,
            "citation_coverage": 0.5,
        }
        result = score_confidence("Tell me about this provision.", chunks, citation_data)
        self.assertEqual((result["level"], result["decision"]), ("medium", "answer_with_caution"))
        displayed = apply_confidence_decision("Original generated answer", result)
        self.assertIn("Caution:", displayed)
        self.assertIn("Original generated answer", displayed)

    def test_abstention_replaces_displayed_answer(self) -> None:
        result = score_confidence("What does Section 4 say?", [self.section3], self.valid_citations)
        self.assertEqual(apply_confidence_decision("Original answer", result), ABSTENTION_MESSAGE)


if __name__ == "__main__":
    unittest.main()

