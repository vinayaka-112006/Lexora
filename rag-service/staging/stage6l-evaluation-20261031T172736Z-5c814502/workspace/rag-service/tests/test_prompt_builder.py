"""Focused tests for grounded answer-format instructions."""
from __future__ import annotations

import sys
import unittest
import re
from pathlib import Path

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.prompt_builder import build_prompt  # noqa: E402
from app.main import _generate_grounded_answer  # noqa: E402
from app.prompt_builder import insert_citation_labels  # noqa: E402
from app.claim_verifier import verify_claims  # noqa: E402


class PromptBuilderTests(unittest.TestCase):
    def test_patent_definition_source_marker_maps_to_indexed_section_two(self) -> None:
        chunk = {
            "chunk_id": "patent-section-2", "document_id": "india:national/patent_act_2024",
            "document_name": "The Patents Act, 1970", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "2",
            "page_start": 8, "page_end": 10,
            "text": '(1) In this Act, unless the context otherwise requires, (m) “patent” means a patent for any invention granted under this Act.',
        }
        messages, citation_map = build_prompt("What is a patent under Indian law?", [chunk])
        self.assertIn("The Patents Act, 1970, section 2, pp. 8-10", messages[1]["content"])
        answer = insert_citation_labels(
            "A patent means a patent for any invention granted under this Act. [S1]", citation_map
        )
        check = verify_claims(answer, [chunk])
        self.assertEqual(citation_map["S1"], "[Source: The Patents Act, 1970, section 2, pp. 8-10]")
        self.assertEqual(check["claims"][0]["status"], "uncertain")
        self.assertTrue(check["claims"][0]["citation_valid"])

    def test_expanded_source_id_uses_canonical_section_two_citation(self) -> None:
        chunk = {
            "chunk_id": "patent-section-2", "document_id": "india:national/patent_act_2024",
            "document_name": "The Patents Act, 1970", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "2",
            "page_start": 8, "page_end": 10,
            "text": '(1) In this Act, (m) “patent” means a patent for any invention granted under this Act.',
        }
        _, citation_map = build_prompt("What is a patent under Indian law?", [chunk])
        answer = insert_citation_labels(
            "A patent means a patent for any invention granted under this Act "
            "(Source: S1, section 3, p. 11).", citation_map
        )
        self.assertIn("[Source: The Patents Act, 1970, section 2, pp. 8-10]", answer)
        self.assertNotIn("section 3, p. 11", answer)
        check = verify_claims(answer, [chunk])
        self.assertEqual(check["claims"][0]["status"], "uncertain")
        self.assertTrue(check["claims"][0]["citation_valid"])
        self.assertEqual(check["claims"][0]["semantic_support"], "not_verified")

    def test_source_id_with_model_added_provision_detail_maps_as_one_citation(self) -> None:
        chunk = {
            "chunk_id": "patent-section-2", "document_name": "The Patents Act, 1970",
            "provision_type": "section", "provision_number": "2", "page_start": 8,
            "page_end": 10, "text": "(1) (m) patent means a patent for any invention granted under this Act.",
        }
        _, citation_map = build_prompt("What is a patent under Indian law?", [chunk])
        answer = insert_citation_labels(
            "A patent is defined in section 2(m) [S1, section 2(m)].", citation_map
        )
        self.assertEqual(answer.count("[Source:"), 1)
        self.assertNotIn("[S1", answer)
        check = verify_claims(answer, [chunk])
        self.assertEqual(check["claims"][0]["status"], "uncertain")
        self.assertTrue(check["claims"][0]["citation_valid"])

    def test_parenthesized_source_id_maps_to_its_retrieved_section(self) -> None:
        chunk = {
            "chunk_id": "patent-section-3", "document_name": "The Patents Act, 1970",
            "provision_type": "section", "provision_number": "3",
            "page_start": 11, "page_end": 12, "text": "(d) known substances; (p) traditional knowledge.",
        }
        _, citation_map = build_prompt("How does this apply to Ayurvedic products?", [chunk])
        answer = insert_citation_labels("Section 3 may apply (S1).", citation_map)
        self.assertIn("[Source: The Patents Act, 1970, section 3, pp. 11-12]", answer)
        check = verify_claims(answer, [chunk])
        self.assertEqual(check["claims"][0]["status"], "uncertain")
        self.assertTrue(check["claims"][0]["citation_valid"])

    def test_single_and_combined_source_ids_expand_in_order(self) -> None:
        citations = {
            "S1": "[Source: The Patents Act, 1970, section 2, pp. 8-10]",
            "S2": "[Source: The Patents Act, 1970, section 3, pp. 11-12]",
            "S3": "[Source: The Patents Act, 1970, section 4, p. 12]",
            "S5": "[Source: TRIPS Agreement, article 27, pp. 13-14]",
        }

        self.assertEqual(
            insert_citation_labels("Claim [S1].", citations),
            f"Claim {citations['S1']}.",
        )
        self.assertEqual(
            insert_citation_labels("Claim [S1, S5].", citations),
            f"Claim {citations['S1']} {citations['S5']}.",
        )
        self.assertEqual(
            insert_citation_labels("Claim [S1, S2, S3].", citations),
            f"Claim {citations['S1']} {citations['S2']} {citations['S3']}.",
        )

    def test_unknown_source_ids_remain_literal_while_known_ids_expand(self) -> None:
        citation = "[Source: The Patents Act, 1970, section 2, pp. 8-10]"

        self.assertEqual(insert_citation_labels("Claim [S99].", {"S1": citation}), "Claim [S99].")
        self.assertEqual(
            insert_citation_labels("Claim [S1, S99].", {"S1": citation}),
            f"Claim {citation} [S99].",
        )

    def test_rule_source_marker_formats_and_verifies_rule_citation(self) -> None:
        chunk = {
            "chunk_id": "patent-rules-133", "document_name": "Patent Rules 2024",
            "jurisdiction": "India", "provision_type": "rule", "provision_number": "133",
            "provision_title": "Supply of certified copies and certificates under sections 72 and 147",
            "page_start": 73, "page_end": 73,
            "text": "Rule 133. Supply of certified copies and certificates under sections 72 and 147.",
        }
        _, citations = build_prompt("What does Rule 133 say?", [chunk])
        self.assertEqual(
            citations["S1"],
            "[Source: Patent Rules 2024, rule 133, pp. 73-73]",
        )
        answer = insert_citation_labels("Rule 133 provides for certified copies [S1, rule 133].", citations)
        self.assertIn(citations["S1"], answer)
        self.assertNotIn("[S1", answer)
        verification = verify_claims(answer, [chunk])
        self.assertTrue(verification["claims"][0]["citation_valid"])
        self.assertEqual(verification["claims"][0]["semantic_support"], "not_verified")

    def test_regulation_source_markers_and_references_use_metadata_citation(self) -> None:
        chunk = {
            "chunk_id": "fssai-regulation-2", "document_name": "FSSAI Ayurveda Aahara Regulations 2022",
            "jurisdiction": "India", "provision_type": "regulation", "provision_number": "2",
            "provision_title": "Definitions", "page_start": 15, "page_end": 15,
            "text": "2. Definitions.- Ayurveda Aahara means food prepared in accordance with these regulations.",
        }
        _, citations = build_prompt("What does Regulation 2 provide?", [chunk])
        expected = "[Source: FSSAI Ayurveda Aahara Regulations 2022, regulation 2, pp. 15-15]"
        self.assertEqual(citations["S1"], expected)
        source_marker = insert_citation_labels(
            "The definition applies (Source: S1, regulation 2, p. 15).",
            citations,
        )
        self.assertEqual(source_marker.count(expected), 1)
        self.assertNotIn("Source: S1", source_marker)
        bracket_marker = insert_citation_labels("The definition applies [S1, regulation 2].", citations)
        self.assertEqual(bracket_marker.count(expected), 1)
        self.assertNotIn("[S1", bracket_marker)
        source_id_marker = insert_citation_labels("Source ID: S1, regulation 2", citations)
        self.assertIn(expected, source_id_marker)
        self.assertNotIn("Source ID: S1", source_id_marker)
        provision_reference = insert_citation_labels("Regulation 2 defines Ayurveda Aahara.", citations)
        self.assertEqual(provision_reference.count(expected), 1)

    def test_explicit_retrieved_provision_without_marker_gets_metadata_citation_only(self) -> None:
        chunk = {
            "chunk_id": "patent-section-3", "document_name": "The Patents Act, 1970",
            "provision_type": "section", "provision_number": "3",
            "page_start": 11, "page_end": 12,
            "text": "(d) known substances without enhanced efficacy. (p) traditional knowledge.",
        }
        _, citation_map = build_prompt("How does this apply to Ayurvedic products?", [chunk])
        answer = insert_citation_labels(
            "The traditional-knowledge exclusion in section 3(p) may apply.", citation_map
        )
        self.assertIn("section 3(p) [Source: The Patents Act, 1970, section 3, pp. 11-12]", answer)
        check = verify_claims(answer, [chunk])
        self.assertEqual(check["claims"][0]["status"], "uncertain")
        self.assertEqual(check["claims"][0]["semantic_support"], "not_verified")

    def test_ayurvedic_follow_up_prompt_selects_indexed_section_2_and_3_clauses(self) -> None:
        chunks = [
            {
                "chunk_id": "patent-section-2", "document_name": "The Patents Act, 1970",
                "provision_type": "section", "provision_number": "2", "page_start": 8,
                "page_end": 10, "text": '(ac) industrial application means capable of being made or used in an industry.\n'
                '(j) invention means a new product or process.\n(ja) inventive step means a feature involving technical advance.',
            },
            {
                "chunk_id": "patent-section-3", "document_name": "The Patents Act, 1970",
                "provision_type": "section", "provision_number": "3", "page_start": 11,
                "page_end": 12, "text": '(a) frivolous inventions.\n'
                '(d) a new form of known substance without enhanced known efficacy.\n'
                '(p) traditional knowledge or duplication of known properties of traditionally known components.',
            },
        ]
        messages, citation_map = build_prompt(
            "Follow-up request: How does this apply to Ayurvedic products? "
            "Context: Patent Act; India jurisdiction; original topic: patent", chunks,
        )
        prompt = messages[1]["content"]
        self.assertIn("USER QUESTION\nHow does this apply to Ayurvedic products?", prompt)
        self.assertIn("Original topic: patent", prompt)
        self.assertIn("India jurisdiction", prompt)
        self.assertIn("traditional knowledge or duplication of known properties", prompt)
        self.assertIn("new form of known substance without enhanced known efficacy", prompt)
        self.assertNotIn("frivolous inventions", prompt)
        self.assertEqual(citation_map["S1"], "[Source: The Patents Act, 1970, section 2, pp. 8-10]")
        self.assertEqual(citation_map["S2"], "[Source: The Patents Act, 1970, section 3, pp. 11-12]")

    def test_simple_words_follow_up_keeps_instruction_and_root_context_in_prompt(self) -> None:
        root = "What is a patent under Indian law?"
        question = (
            "Explain in simple words\n\nContext: Patent Act; India jurisdiction; "
            f"original question: {root}; original topic: patent"
        )
        messages, _ = build_prompt(question, [])
        prompt = messages[1]["content"]
        self.assertIn("Original question: What is a patent under Indian law?", prompt)
        self.assertIn("Original topic: patent", prompt)
        self.assertIn("India jurisdiction", prompt)
        self.assertIn("USER QUESTION\nExplain in simple words", prompt)
        self.assertEqual(prompt.count("Original question:"), 1)

    def test_generated_answer_does_not_append_a_duplicate_source_list(self) -> None:
        class FakeLLM:
            def generate(self, _messages: list[dict[str, str]]) -> str:
                return "The available text does not define the requested term."

        answer = _generate_grounded_answer(
            "What is a patent?",
            [{"text": "Evidence text.", "document_name": "Patent Act", "jurisdiction": "India",
              "provision_type": "section", "provision_number": "2", "page_start": 1, "page_end": 2}],
            FakeLLM(),
        )
        self.assertEqual(answer, "The available text does not define the requested term.")

    def test_supported_answer_prompt_is_concise_and_preserves_qualifications(self) -> None:
        messages, citations = build_prompt(
            "What is a patent under Indian law?",
            [{
                "text": "A patent means a patent for any invention granted under this Act.",
                "jurisdiction": "India",
                "document_name": "Patents Act",
                "provision_type": "section",
                "provision_number": "2",
                "page_start": 1,
                "page_end": 2,
            }],
        )

        self.assertEqual([message["role"] for message in messages], ["system", "user"])
        prompt = re.sub(r"\s+", " ", " ".join(message["content"] for message in messages)).lower()
        self.assertIn("directly answer the question in a few sentences", prompt)
        self.assertIn("preserve material legal conditions, exceptions, limits, and qualifications", prompt)
        self.assertIn("traditional-knowledge exclusion", prompt)
        self.assertIn("one coherent answer", prompt)
        self.assertIn("only the supplied source references", prompt)
        self.assertIn("[s1]", prompt)
        self.assertEqual(citations["S1"], "[Source: Patents Act, section 2, pp. 1-2]")

    def test_insufficient_or_unrelated_evidence_prompt_requires_limitation(self) -> None:
        messages, citations = build_prompt("What is a patent?", [])
        prompt = re.sub(r"\s+", " ", " ".join(message["content"] for message in messages)).lower()

        self.assertIn("[no retrieved legal sources.]", prompt)
        self.assertIn("if the context does not adequately answer the question", prompt)
        self.assertIn("if support is missing, answer only", prompt)
        self.assertIn("conflicting, or unrelated", prompt)
        self.assertEqual(citations, {})


if __name__ == "__main__":
    unittest.main()
