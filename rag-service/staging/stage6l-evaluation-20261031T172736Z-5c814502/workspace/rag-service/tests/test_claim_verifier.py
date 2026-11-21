"""Tests for deterministic claim extraction and citation/evidence coverage."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.claim_verifier import verify_claims  # noqa: E402


class ClaimVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patent = {
            "chunk_id": "patent-section-3", "document_name": "Patents Act 2024",
            "provision_type": "section", "provision_number": "3",
            "page_start": 11, "page_end": 12,
            "text": "Certain subject matter is excluded from patentability.",
        }
        self.valid = "[Source: Patents Act 2024, section 3, pp. 11-12]"
        self.invalid = "[Source: Patents Act 2024, section 4, pp. 13-14]"

    def test_valid_citation_is_uncertain_not_semantically_supported(self) -> None:
        result = verify_claims(f"Section 3 excludes certain subject matter. {self.valid}", [self.patent])
        claim = result["claims"][0]
        self.assertEqual(claim["status"], "uncertain")
        self.assertTrue(claim["citation_valid"])
        self.assertTrue(claim["evidence_found"])
        self.assertEqual(claim["semantic_support"], "not_verified")

    def test_sentence_without_citation_is_unsupported(self) -> None:
        result = verify_claims("Section 3 excludes certain subject matter.", [self.patent])
        self.assertEqual(result["claims"][0]["status"], "unsupported")
        self.assertEqual(result["claims"][0]["citations"], [])

    def test_invalid_citation_is_unsupported(self) -> None:
        result = verify_claims(f"Unsupported proposition. {self.invalid}", [self.patent])
        self.assertEqual(result["claims"][0]["status"], "unsupported")
        self.assertFalse(result["claims"][0]["evidence_found"])

    def test_mixed_claim_coverage(self) -> None:
        answer = f"One claim. {self.valid}\nAnother claim has no citation."
        result = verify_claims(answer, [self.patent])
        self.assertEqual(result["claim_count"], 2)
        self.assertEqual(result["citation_coverage"], 0.5)
        self.assertEqual(result["overall_status"], "partial_citation_coverage")

    def test_multiple_citations_associated_with_one_claim(self) -> None:
        other = dict(self.patent, chunk_id="patent-section-4", provision_number="4", page_start=13, page_end=14)
        citation2 = "[Source: Patents Act 2024, section 4, pp. 13-14]"
        result = verify_claims(f"A combined claim. {self.valid} {citation2}", [self.patent, other])
        self.assertEqual(len(result["claims"][0]["citations"]), 2)
        self.assertTrue(result["claims"][0]["citation_valid"])

    def test_citation_only_continuation_attaches_to_previous_claim(self) -> None:
        result = verify_claims(f"A claim without inline citation.\n{self.valid}", [self.patent])
        self.assertEqual(result["claim_count"], 1)
        self.assertEqual(result["claims"][0]["status"], "uncertain")

    def test_headings_are_ignored(self) -> None:
        result = verify_claims(f"## Summary\nA factual claim. {self.valid}\nSources:", [self.patent])
        self.assertEqual(result["claim_count"], 1)

    def test_empty_answer(self) -> None:
        result = verify_claims(" \n", [self.patent])
        self.assertEqual(result["claim_count"], 0)
        self.assertEqual(result["citation_coverage"], 0.0)
        self.assertEqual(result["overall_status"], "insufficient_citation_coverage")

    def test_repeated_input_is_deterministic(self) -> None:
        answer = f"Claim text. {self.valid}"
        self.assertEqual(verify_claims(answer, [self.patent]), verify_claims(answer, [self.patent]))

    def test_coverage_status_does_not_claim_semantic_verification(self) -> None:
        result = verify_claims(f"Claim one. {self.valid}\nClaim two. {self.valid}", [self.patent])
        self.assertEqual(result["citation_coverage"], 1.0)
        self.assertEqual(result["overall_status"], "complete_citation_coverage")
        self.assertEqual(result["supported_claims"], 0)
        self.assertEqual(result["uncertain_claims"], 2)

    def test_zero_coverage_overall_status(self) -> None:
        result = verify_claims("Claim one.\nClaim two.", [self.patent])
        self.assertEqual(result["citation_coverage"], 0.0)
        self.assertEqual(result["overall_status"], "insufficient_citation_coverage")


if __name__ == "__main__":
    unittest.main()
