"""Standard-library tests for deterministic citation integrity validation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.citation_validator import validate_citations  # noqa: E402


class CitationValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patent = {
            "chunk_id": "patent-section-3",
            "document_name": "Patents Act 2024",
            "provision_type": "section",
            "provision_number": "3",
            "page_start": 11,
            "page_end": 12,
            "jurisdiction": "India",
        }
        self.nagoya = {
            "chunk_id": "nagoya-article-3",
            "document_name": "Nagoya Protocol",
            "provision_type": "article",
            "provision_number": "3",
            "page_start": 5,
            "page_end": 6,
            "jurisdiction": "International",
        }

    def test_valid_citation(self) -> None:
        answer = "Certain subject matter is excluded.\n[Source: Patents Act 2024, section 3, pp. 11-12]"
        result = validate_citations(answer, [self.patent])
        self.assertTrue(result["valid"])
        self.assertEqual(result["citation_coverage"], 1.0)
        self.assertEqual(result["citations"][0]["matched_chunk_ids"], ["patent-section-3"])

    def test_wrong_provision(self) -> None:
        result = validate_citations(
            "[Source: Patents Act 2024, section 4, pp. 13-14]", [self.patent]
        )
        self.assertFalse(result["citations"][0]["valid"])

    def test_subsection_and_clause_citation_matches_parent_section_chunk(self) -> None:
        chunk = {
            "chunk_id": "patent-section-2", "document_name": "The Patents Act, 1970",
            "provision_type": "section", "provision_number": "2",
            "page_start": 8, "page_end": 10,
            "text": '(1) In this Act, (m) “patent” means a patent for any invention granted under this Act.',
        }
        result = validate_citations(
            "[Source: The Patents Act, 1970, section 2(1)(m), pp. 9-9]", [chunk]
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["citations"][0]["matched_chunk_ids"], ["patent-section-2"])
        invalid = validate_citations(
            "[Source: The Patents Act, 1970, section 2(1)(zz), pp. 9-9]", [chunk]
        )
        self.assertFalse(invalid["valid"])

    def test_wrong_document(self) -> None:
        result = validate_citations(
            "[Source: Trade Marks Act, section 3, pp. 11-12]", [self.patent]
        )
        self.assertFalse(result["citations"][0]["valid"])

    def test_section_does_not_match_article(self) -> None:
        result = validate_citations(
            "[Source: Nagoya Protocol, section 3, pp. 5-6]", [self.nagoya]
        )
        self.assertFalse(result["citations"][0]["valid"])

    def test_rule_citation_matches_only_the_same_rule_metadata(self) -> None:
        rule = {
            "chunk_id": "patent-rules-133", "document_name": "Patent Rules 2024",
            "provision_type": "rule", "provision_number": "133",
            "page_start": 73, "page_end": 73,
        }
        answer = "[Source: Patent Rules 2024, rule 133, pp. 73-73]"
        result = validate_citations(answer, [rule])
        self.assertTrue(result["valid"])
        self.assertEqual(result["citations"][0]["matched_chunk_ids"], ["patent-rules-133"])
        wrong_type = validate_citations(
            "[Source: Patent Rules 2024, section 133, pp. 73-73]", [rule]
        )
        self.assertFalse(wrong_type["valid"])

    def test_regulation_citation_matches_regulation_metadata(self) -> None:
        regulation = {
            "chunk_id": "fssai-regulation-2", "document_name": "FSSAI Ayurveda Aahara Regulations 2022",
            "provision_type": "regulation", "provision_number": "2",
            "page_start": 15, "page_end": 15,
        }
        result = validate_citations(
            "[Source: FSSAI Ayurveda Aahara Regulations 2022, regulation 2, pp. 15-15]",
            [regulation],
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["citations"][0]["matched_chunk_ids"], ["fssai-regulation-2"])
        wrong_type = validate_citations(
            "[Source: FSSAI Ayurveda Aahara Regulations 2022, section 2, pp. 15-15]",
            [regulation],
        )
        self.assertFalse(wrong_type["valid"])

    def test_wrong_page_range(self) -> None:
        result = validate_citations(
            "[Source: Patents Act 2024, section 3, pp. 50-51]", [self.patent]
        )
        self.assertFalse(result["citations"][0]["valid"])

    def test_overlapping_page_range_and_case_whitespace_normalization(self) -> None:
        result = validate_citations(
            "[source:  PATENTS   ACT 2024, SECTION 3, pp. 12-13]", [self.patent]
        )
        self.assertTrue(result["citations"][0]["valid"])

    def test_document_only_citation(self) -> None:
        chunk = {
            "chunk_id": "contents-page",
            "document_name": "Patent Act 2024",
            "provision_type": None,
            "provision_number": None,
            "page_start": 1,
            "page_end": 2,
        }
        result = validate_citations("[Source: Patent Act 2024, p. 1-2]", [chunk])
        self.assertTrue(result["valid"])
        self.assertEqual(result["valid_citations"], 1)
    def test_no_citation_has_zero_coverage(self) -> None:
        result = validate_citations(
            "Section 3 excludes certain subject matter from patentability.", [self.patent]
        )
        self.assertEqual(result["citation_count"], 0)
        self.assertEqual(result["citation_coverage"], 0.0)
        self.assertFalse(result["valid"])

    def test_malformed_citation_is_reported(self) -> None:
        result = validate_citations("[Source: Patents Act 2024, section 3]", [self.patent])
        self.assertEqual(result["citation_count"], 1)
        self.assertFalse(result["citations"][0]["valid"])
        self.assertTrue(any("Malformed citation" in error for error in result["errors"]))

    def test_multiple_valid_citations(self) -> None:
        answer = (
            "[Source: Patents Act 2024, section 3, pp. 11-12]\n"
            "[Source: Nagoya Protocol, article 3, pp. 5-6]"
        )
        result = validate_citations(answer, [self.patent, self.nagoya])
        self.assertEqual(result["total_citations"], 2)
        self.assertEqual(result["valid_citations"], 2)
        self.assertEqual(result["citation_coverage"], 1.0)

    def test_answer_is_not_modified(self) -> None:
        answer = "Text. [Source: Patents Act 2024, section 3, pp. 11-12]"
        before = answer[:]
        validate_citations(answer, [self.patent])
        self.assertEqual(answer, before)


if __name__ == "__main__":
    unittest.main()

