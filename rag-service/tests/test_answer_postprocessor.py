"""Tests for consistent, citation-aware answer rendering in API and CLI."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.answer_postprocessor import postprocess_generated_answer  # noqa: E402


class AnswerPostprocessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.section3 = {
            "chunk_id": "section-3", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "3",
            "page_start": 6, "page_end": 6,
            "text": "Section 3 lists persons requiring prior approval of the National Biodiversity Authority.",
        }

    def test_keeps_citation_matched_claim_and_withholds_uncited_assumption(self) -> None:
        answer = (
            "Section 3 lists specified persons who need prior approval. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]\n"
            "You are a non-resident of India."
        )
        result = postprocess_generated_answer("Explain Section 3", answer, [self.section3])
        self.assertEqual(result["confidence"]["decision"], "answer_with_caution")
        self.assertIn("Section 3 lists specified persons", result["answer"])
        self.assertNotIn("non-resident", result["answer"])
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)
        self.assertEqual(result["claim_verification"]["unsupported_claims"], 0)
        self.assertEqual(result["claim_verification"]["claims"][0]["status"], "uncertain")
        self.assertEqual(result["claim_verification"]["semantic_support"], "not_verified")
        self.assertEqual(result["validation"]["valid_citations"], 1)
        self.assertTrue(result["warnings"])

    def test_withholds_all_claims_when_no_citation_matches_retrieved_source(self) -> None:
        answer = (
            "Every Indian citizen needs NBA approval. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer("Explain Section 3", answer, [self.section3])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("Every Indian citizen", result["answer"])
        self.assertEqual(result["claim_verification"]["claims"], [])
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)
        self.assertEqual(result["validation"]["citation_count"], 1)
        self.assertFalse(result["validation"]["citations"][0]["valid"])
        diagnostic = result["claim_verification"]["generated_claims"][0]
        self.assertEqual(diagnostic["text"], "Every Indian citizen needs NBA approval.")
        self.assertEqual(len(diagnostic["citations"]), 1)
        self.assertFalse(diagnostic["citation_results"][0]["valid"])
        self.assertFalse(diagnostic["retained"])
        self.assertIn("citation_not_mapped_to_retrieved_evidence", diagnostic["withheld_reasons"])
        self.assertEqual(
            diagnostic["citation_errors"], ["Citation does not match any retrieved evidence."]
        )
        self.assertEqual(
            result["claim_verification"]["original_validation"], result["validation"]
        )

    def test_preserves_safety_guard_and_matched_source_for_withheld_claim(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "No person, other than a person covered under sub-section (2) of section 3 shall access biological resources without prior intimation. Provided that this section shall not apply to cultivated medicinal plants; a certificate of origin is required.",
        }
        answer = (
            "As an Indian citizen, you are exempt from prior intimation under Section 7. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer(
            "I am an Indian citizen. What does Section 7 require?", answer, [section7]
        )
        diagnostic = result["claim_verification"]["generated_claims"][0]
        self.assertFalse(diagnostic["retained"])
        self.assertIn("safety_guard:citizenship_section7_exemption", diagnostic["withheld_reasons"])
        self.assertEqual(diagnostic["matched_sources"][0]["chunk_id"], "section-7")

    def test_withholds_a_cited_direct_assumption_about_unstated_residency(self) -> None:
        answer = (
            "As a non-resident of India, you need prior approval. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer(
            "I want to collect Ashwagandha in Karnataka for commercial sale.",
            answer,
            [self.section3],
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("non-resident", result["answer"])
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)

    def test_preserves_a_conditional_residency_rule(self) -> None:
        answer = (
            "If you are a non-resident, Section 3 may require prior approval. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer(
            "What does Section 3 say?", answer, [self.section3]
        )
        self.assertEqual(result["claim_verification"]["claims"][0]["status"], "uncertain")
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 0)

    def test_withholds_citizenship_as_the_only_section7_exemption_basis(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "Prior intimation is required. Provided that this section shall not apply to cultivated medicinal plants; the exemption requires a certificate of origin from the BMC.",
        }
        answer = (
            "As an Indian citizen, you are exempt from prior intimation under Section 7. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer(
            "I am an Indian citizen. What does Section 7 require?", answer, [section7]
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("you are exempt", result["answer"])
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)

    def test_deduplicates_only_adjacent_identical_metadata_citations(self) -> None:
        answer = (
            "Section 3 describes specified persons. [Source: Biological Diversity Act 2002, section 3, pp. 6-6] "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer("Explain Section 3", answer, [self.section3])
        self.assertEqual(result["answer"].count("[Source:"), 1)
        self.assertIn("specified persons", result["answer"])

    def test_deduplicates_citations_again_after_withheld_claims_are_removed(self) -> None:
        citation = "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        answer = (
            f"Section 3 lists specified persons who need prior approval. {citation} {citation}\n"
            "You are a non-resident of India."
        )
        result = postprocess_generated_answer(
            "Explain Section 3", answer, [self.section3]
        )
        self.assertEqual(result["confidence"]["decision"], "answer_with_caution")
        self.assertEqual(result["answer"].count("[Source:"), 1)

    def test_withholds_section3_approval_claim_that_omits_person_categories(self) -> None:
        section3 = {
            **self.section3,
            "text": "The persons who shall be required to take approval are: a person who is not a citizen of India; a citizen who is a non-resident; a body corporate incorporated outside India or controlled by a foreigner.",
        }
        answer = (
            "Section 3 requires prior approval from the National Biodiversity Authority for accessing biological resources. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer("What permissions apply?", answer, [section3])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)
        self.assertNotIn("requires prior approval", result["answer"])

    def test_withholds_broad_section3_access_summary_without_person_categories(self) -> None:
        section3 = {
            **self.section3,
            "text": (
                "The persons who shall be required to take approval are a person who is not a citizen of India; "
                "a citizen who is a non-resident; and a body corporate incorporated outside India or controlled by a foreigner."
            ),
        }
        answer = (
            "Section 3 regulates access to biological resources, including cultivated medicinal plants, for commercial utilisation. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer("Explain the relevance of Section 3.", answer, [section3])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertIn(
            "bda_section3_scope",
            result["claim_verification"]["generated_claims"][0]["safety_guards"],
        )

    def test_withholds_section7_prior_intimation_claim_that_omits_scope_and_exceptions(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "No person, other than a person covered under sub-section (2) of section 3 shall access biological resources for commercial utilisation without prior intimation. Provided that this section shall not apply to cultivated medicinal plants. A certificate of origin is required from the BMC.",
        }
        answer = (
            "Section 7 requires prior intimation for commercial access to biological resources. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer("What does Section 7 require?", answer, [section7])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("requires prior intimation", result["answer"])

    def test_withholds_section7_claim_that_inverts_person_category_scope(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "No person, other than a person covered under sub-section (2) of section 3 shall access biological resources for commercial utilisation without prior intimation. Provided that this section shall not apply to cultivated medicinal plants. A certificate of origin is required from the BMC.",
        }
        answer = (
            "As an Indian citizen, you are not subject to Section 7 prior intimation, "
            "which applies to non-Indian citizens and non-resident Indians. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer(
            "I am an Indian citizen. What requirements apply?", answer, [section7]
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("not subject to Section 7", result["answer"])
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)

    def test_withholds_section3_claim_that_treats_citizenship_alone_as_exemption(self) -> None:
        section3 = {
            **self.section3,
            "text": (
                "The persons who shall be required to take the approval are: a person who is not a citizen of India; "
                "a citizen of India who is a non -resident; and a body corporate incorporated outside India or "
                "controlled by a foreigner."
            ),
        }
        answer = (
            "As an Indian citizen, you are not required to obtain prior approval from the National Biodiversity "
            "Authority under Section 3 of the Biological Diversity Act, 2002, since you are a citizen of India. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer(
            "I am an Indian citizen starting a company. What permissions apply?", answer, [section3]
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("not required to obtain prior approval", result["answer"])
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)

    def test_withholds_section3_personal_status_claim_when_company_control_is_unaddressed(self) -> None:
        section3 = {
            **self.section3,
            "text": (
                "The persons who shall be required to take approval are a person who is not a citizen of India; "
                "a citizen who is a non-resident; and a body corporate incorporated outside India or "
                "controlled by a foreigner."
            ),
        }
        answer = (
            "As an Indian citizen, you are not required to obtain prior approval from the National Biodiversity "
            "Authority under Section 3, as you are not a non-resident or a foreigner. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer(
            "I am an Indian citizen starting an Ayurvedic company. What requirements apply?",
            answer,
            [section3],
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("not required to obtain prior approval", result["answer"])

    def test_withholds_citizenship_based_section3_conclusion_when_residence_is_unstated(self) -> None:
        section3 = {
            **self.section3,
            "text": (
                "The persons who shall be required to take approval are a person who is not a citizen of India; "
                "a citizen who is a non -resident; and a body corporate incorporated outside India or "
                "controlled by a foreigner."
            ),
        }
        answer = (
            "As an Indian citizen, you are not subject to the provisions of section 3(2), "
            "which applies to non-citizens and non-resident Indians. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer("I am an Indian citizen. What applies?", answer, [section3])
        self.assertNotIn("not subject to the provisions", result["answer"])
        self.assertIn(
            "bda_section3_citizenship_residence",
            result["claim_verification"]["generated_claims"][0]["safety_guards"],
        )

    def test_withholds_definite_cultivated_exemption_without_certificate_condition(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": (
                "Provided that this section shall not apply to cultivated medicinal plants. "
                "The exemption is available only if a certificate of origin is obtained from the BMC."
            ),
        }
        answer = (
            "As the farmer cultivates the roots on private agricultural land, the exemption under Section 7(2) is available. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer(
            "Does Section 7 apply to cultivated Ashwagandha?", answer, [section7]
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("exemption under Section 7(2) is available", result["answer"])
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)
        self.assertIn(
            "bda_section7_missing_certificate_condition",
            result["claim_verification"]["generated_claims"][0]["safety_guards"],
        )

    def test_withholds_claim_that_certificate_is_not_required_for_cultivated_exemption(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": (
                "This section shall not apply to cultivated medicinal plants. "
                "The exemption is available only if a certificate of origin is obtained from the BMC."
            ),
        }
        answer = (
            "You may not be required to obtain a certificate of origin because the exemption may apply to cultivated roots. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer(
            "What conditions apply to cultivated Ashwagandha?", answer, [section7]
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("not be required to obtain a certificate", result["answer"])
        self.assertIn(
            "bda_section7_missing_certificate_condition",
            result["claim_verification"]["generated_claims"][0]["safety_guards"],
        )

    def test_withholds_claim_that_attributes_bmc_certificate_to_the_plant_source(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": (
                "This section shall not apply to cultivated medicinal plants. "
                "A certificate of origin shall be obtained from the Biodiversity Management Committee."
            ),
        }
        answer = (
            "The cultivated medicinal plants must be obtained from the Biodiversity Management Committee, and the certificate of origin obtained in the prescribed manner. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer("What conditions apply?", answer, [section7])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("plants must be obtained from the Biodiversity Management Committee", result["answer"])
        self.assertIn(
            "bda_section7_misattributes_bmc_certificate",
            result["claim_verification"]["generated_claims"][0]["safety_guards"],
        )

    def test_abstention_names_missing_forest_law_evidence(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "This section shall not apply to cultivated medicinal plants; certificate of origin conditions apply.",
        }
        result = postprocess_generated_answer(
            "I want to commercially collect wild plants from forest land. What permissions apply?",
            "The retrieved text does not answer the forest permission question.",
            [self.section3, section7],
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertIn("do not include provisions addressing commercial collection from forest land", result["answer"])
        self.assertIn("I cannot determine those permissions from this evidence.", result["answer"])

    def test_forest_gap_message_is_not_used_when_a_forest_law_source_is_retrieved(self) -> None:
        forest_source = {
            "chunk_id": "forest-section", "document_id": "india:national/indian_forest_act",
            "document_name": "Indian Forest Act", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "26", "page_start": 1, "page_end": 1,
            "text": "Restrictions apply to forest produce.",
        }
        result = postprocess_generated_answer(
            "I want to commercially collect wild plants from forest land. What permissions apply?",
            "Section 26 restricts forest produce. [Source: Indian Forest Act, section 26, pp. 1-1]",
            [forest_source],
        )
        self.assertNotIn("do not include provisions addressing commercial collection", result["answer"])

    def test_withholds_person_specific_cultivated_exemption_claim_missing_certificate_condition(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "No person, other than a person covered under sub-section (2) of section 3 shall access biological resources without prior intimation. Provided that this section shall not apply to cultivated medicinal plants; a certificate of origin is required.",
        }
        answer = (
            "Since you are an Indian citizen and the farmer is a local cultivator, it is possible that the exemption under Section 7 may apply. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer(
            "I am an Indian citizen buying cultivated Ashwagandha. What applies?", answer, [section7]
        )
        self.assertNotIn("the exemption under Section 7 may apply", result["answer"])
        self.assertIn(
            "citizenship_section7_exemption",
            result["claim_verification"]["generated_claims"][0]["safety_guards"],
        )

    def test_withholds_inverted_section3_category_list(self) -> None:
        section3 = {
            **self.section3,
            "text": (
                "The persons who shall be required to take the approval are a person who is not a citizen of India; "
                "a citizen who is a non-resident; and a body corporate incorporated outside India or "
                "controlled by a foreigner."
            ),
        }
        answer = (
            "Obtain prior approval from the NBA under Section 3 if you are not an Indian citizen, "
            "non-resident Indian, or a body corporate controlled by foreigners. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        result = postprocess_generated_answer("What permissions apply?", answer, [section3])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("if you are not an Indian citizen", result["answer"])

    def test_withholds_prior_intimation_claim_for_cultivated_roots_without_exception_conditions(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": (
                "No person, other than a person covered under sub-section (2) of section 3 shall access "
                "biological resources for commercial utilisation without prior intimation. Provided that this "
                "section shall not apply to cultivated medicinal plants. In the case of cultivated medicinal "
                "plants, exemption is available only with a certificate of origin from the BMC."
            ),
        }
        answer = (
            "You would need to obtain prior intimation from the concerned State Biodiversity Board under "
            "Section 7 for access to cultivated Ashwagandha roots. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer(
            "I plan to buy cultivated Ashwagandha roots. What applies?", answer, [section7]
        )
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("prior intimation from the concerned", result["answer"])
        self.assertEqual(result["claim_verification"]["withheld_claim_count"], 1)

    def test_withholds_section7_exemption_misrepresented_as_act_wide(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "No person, other than a person covered under sub-section (2) of section 3 shall access biological resources without prior intimation. Provided that this section shall not apply to cultivated medicinal plants. Exemption is available only if a certificate of origin is obtained from the BMC.",
        }
        answer = (
            "The Biological Diversity Act does not apply to cultivated medicinal plants and their products. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer("What applies to cultivated plants?", answer, [section7])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("Biological Diversity Act does not apply", result["answer"])

    def test_withholds_claim_that_denies_the_cultivated_plant_exception(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "No person, other than a person covered under sub-section (2) of section 3 shall access biological resources without prior intimation. Provided that this section shall not apply to cultivated medicinal plants; a certificate of origin is required.",
        }
        answer = (
            "Additionally, the Act does not provide a specific exemption for cultivated medicinal plants and their products, as mentioned in Section 7. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer("What applies to wild collection?", answer, [section7])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("does not provide a specific exemption", result["answer"])
        diagnostic = result["claim_verification"]["generated_claims"][0]
        self.assertIn("bda_section7_denies_cultivated_exception", diagnostic["safety_guards"])
        self.assertEqual(diagnostic["verification_status"], "uncertain")

    def test_withholds_person_specific_section7_conclusion_without_section3_category_qualification(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "No person, other than a person covered under sub-section (2) of section 3 shall access biological resources without prior intimation. Provided that this section shall not apply to cultivated medicinal plants; a certificate of origin is required.",
        }
        answer = "Section 7 applies to your situation. [Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        result = postprocess_generated_answer("I am starting an Indian company. What applies?", answer, [section7])
        self.assertNotIn("applies to your situation", result["answer"])
        self.assertIn(
            "bda_section7_scope",
            result["claim_verification"]["generated_claims"][0]["safety_guards"],
        )

    def test_withholds_citation_labeled_incomplete_heading(self) -> None:
        answer = "The applicable person categories under Section 7 are: [Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        result = postprocess_generated_answer("Explain Section 7", answer, [self.section3])
        self.assertNotIn("person categories under Section 7 are:", result["answer"])
        self.assertIn(
            "incomplete_statement",
            result["claim_verification"]["generated_claims"][0]["safety_guards"],
        )

    def test_withholds_section7_mislabelled_as_nba_prior_approval(self) -> None:
        section7 = {
            "chunk_id": "section-7", "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7", "page_start": 7, "page_end": 8,
            "text": "No person, other than a person covered under sub-section (2) of section 3 shall access biological resources for commercial utilisation without prior intimation to the concerned State Biodiversity Board. Provided that this section shall not apply to cultivated medicinal plants. Exemption requires certificate of origin from BMC.",
        }
        answer = (
            "The farmer would not be required to obtain prior approval from the NBA under Section 7(2). "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        result = postprocess_generated_answer("What does Section 7 require?", answer, [section7])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        self.assertNotIn("prior approval from the NBA", result["answer"])


class FabricatedInstrumentGuardTests(unittest.TestCase):
    """Test that hallucinated state regulations and unverified named instruments are withheld."""

    def _bda_section7_chunk(self) -> dict:
        return {
            "chunk_id": "bda-s7", "document_id": "biological_diversity_act_2002",
            "document_name": "Biological Diversity Act, 2002", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "7",
            "page_start": 7, "page_end": 8,
            "text": (
                "No person, other than those referred to in Section 3(2), shall, without prior intimation "
                "to the State Biodiversity Board, obtain any biological resource occurring in India or "
                "knowledge associated thereto for commercial utilisation. "
                "Provided that the provisions of this section shall not apply in relation to cultivated "
                "medicinal plants and their products where a certificate of origin is obtained."
            ),
        }

    def test_hallucinated_state_biodiversity_regulations_are_withheld(self) -> None:
        """Claims naming 'Karnataka State Biodiversity Board Regulations, 2004' must be withheld."""
        answer = (
            "Under the Karnataka State Biodiversity Board Regulations, 2004, "
            "prior registration with the KSBB is mandatory for all commercial users. "
            "[Source: Biological Diversity Act, 2002, section 7, pp. 7-8]"
        )
        chunks = [self._bda_section7_chunk()]
        result = postprocess_generated_answer(
            "What permits are needed for Ashwagandha in Karnataka?",
            answer,
            chunks,
        )
        self.assertNotIn("Karnataka State Biodiversity Board Regulations, 2004", result["answer"])

    def test_known_corpus_instruments_are_not_withheld(self) -> None:
        """Claims correctly citing a corpus instrument (Biological Diversity Act, 2002) are retained."""
        answer = (
            "Under Section 7 of the Biological Diversity Act, 2002, prior intimation to the "
            "State Biodiversity Board is required for commercial utilisation. "
            "[Source: Biological Diversity Act, 2002, section 7, pp. 7-8]"
        )
        chunks = [self._bda_section7_chunk()]
        result = postprocess_generated_answer(
            "What does the Biological Diversity Act require?",
            answer,
            chunks,
        )
        self.assertIn("Biological Diversity Act, 2002", result["answer"])
        self.assertNotEqual(result["confidence"]["decision"], "abstain")

    def test_hallucinated_maharashtra_regulation_withheld(self) -> None:
        """Claims naming 'Maharashtra Biodiversity Board Rules, 2008' must be withheld."""
        answer = (
            "The Maharashtra Biodiversity Board Rules, 2008 also apply to this transaction. "
            "[Source: Biological Diversity Act, 2002, section 7, pp. 7-8]"
        )
        chunks = [self._bda_section7_chunk()]
        result = postprocess_generated_answer(
            "What permits are needed in Maharashtra?",
            answer,
            chunks,
        )
        self.assertNotIn("Maharashtra Biodiversity Board Rules, 2008", result["answer"])

    def test_fabricated_guard_does_not_trigger_on_non_state_instruments(self) -> None:
        """The fabricated_legal_instrument guard must not fire on the Biological Diversity Act, 2002."""
        from app.answer_postprocessor import _asserts_fabricated_legal_instrument
        # A claim referencing the Biological Diversity Act, 2002 (a known corpus instrument)
        claim = "Section 7 of the Biological Diversity Act, 2002 requires prior intimation."
        chunks = [self._bda_section7_chunk()]
        # The fabricated_legal_instrument guard specifically must NOT fire for this claim
        self.assertFalse(
            _asserts_fabricated_legal_instrument(claim, chunks),
            "Biological Diversity Act, 2002 is a known corpus instrument and must not be flagged as fabricated",
        )

    def test_fabricated_guard_does_not_trigger_on_patents_act(self) -> None:
        """The fabricated_legal_instrument guard must not fire on the Patents Act, 1970."""
        from app.answer_postprocessor import _asserts_fabricated_legal_instrument
        claim = "Under Section 3(p) of the Patents Act, 1970, traditional knowledge is excluded."
        chunks = []
        self.assertFalse(
            _asserts_fabricated_legal_instrument(claim, chunks),
            "Patents Act, 1970 is a known corpus instrument and must not be flagged as fabricated",
        )


class CitationDocumentFamilyTests(unittest.TestCase):
    """Test that the prompt builder does not attach cross-Act citations."""

    def setUp(self) -> None:
        import sys, pathlib
        rag_root = pathlib.Path(__file__).resolve().parents[1]
        if str(rag_root) not in sys.path:
            sys.path.insert(0, str(rag_root))
        from app.prompt_builder import insert_citation_labels
        self.insert = insert_citation_labels

    def _patents_citation(self, section: str = "3", pp: str = "11-12") -> dict:
        return {
            "S1": f"[Source: The Patents Act, 1970, section {section}, pp. {pp}]",
        }

    def _bda_citation(self, section: str = "7", pp: str = "7-8") -> dict:
        return {
            "S1": f"[Source: Biological Diversity Act, 2002, section {section}, pp. {pp}]",
        }

    def test_bda_citation_not_injected_into_patents_act_sentence(self) -> None:
        """A BDA citation must NOT be auto-linked onto a sentence discussing Patents Act Section 3."""
        # Sentence explicitly discusses patentability under the Patents Act
        answer = (
            "Under section 3 of the Patents Act, 1970, traditional knowledge-based inventions "
            "may be excluded from patentability."
        )
        result = self.insert(answer, self._bda_citation(section="3", pp="6-6"))
        # The BDA section 3 citation must not appear attached to this sentence
        self.assertNotIn("Biological Diversity Act", result,
                         "BDA citation must not be injected into a Patents Act sentence")

    def test_patents_citation_not_injected_into_bda_sentence(self) -> None:
        """A Patents Act citation must NOT be auto-linked onto a sentence about BDA Section 3."""
        answer = (
            "Under section 3 of the Biological Diversity Act, 2002, prior approval from the "
            "National Biodiversity Authority is required for certain persons."
        )
        result = self.insert(answer, self._patents_citation(section="3", pp="11-12"))
        # The Patents Act citation must not be appended here
        self.assertNotIn("The Patents Act", result,
                         "Patents Act citation must not be injected into a BDA sentence")

    def test_correct_bda_citation_appended_to_bda_sentence(self) -> None:
        """A BDA citation for section 7 should be attached to a correct BDA section 7 sentence."""
        answer = (
            "Prior intimation to the State Biodiversity Board is required under section 7 "
            "for commercial utilisation of biological resources."
        )
        result = self.insert(answer, self._bda_citation(section="7", pp="7-8"))
        # The BDA section 7 citation should be present (either via marker expansion or auto-link)
        self.assertIn("Biological Diversity Act", result)

    def test_explicit_source_marker_always_resolved_regardless_of_family(self) -> None:
        """When the model writes [S1] explicitly, it must always be resolved."""
        answer = "Ashwagandha is excluded under section 3(p). [S1]"
        result = self.insert(answer, self._patents_citation(section="3", pp="11-12"))
        self.assertIn("The Patents Act, 1970", result)
        self.assertNotIn("[S1]", result)


if __name__ == "__main__":
    unittest.main()
