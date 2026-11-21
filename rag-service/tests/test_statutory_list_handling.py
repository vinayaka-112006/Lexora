"""Regression tests for statutory list fragment handling and patentability retrieval.

Covers:
- Section 3 bullet items not rejected merely for being grammatical fragments
- Introductory headings ending in ':' still correctly withheld
- Patentability-query detection in analyze_legal_query / retriever
- Original claim diagnostics preserved on total abstention
- Citation/rejection reasons preserved correctly
- Mixed retained/withheld claim handling
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.answer_postprocessor import (  # noqa: E402
    _is_incomplete_statement,
    postprocess_generated_answer,
)
from app.retriever import analyze_legal_query, LegalRetriever  # noqa: E402


# ---------------------------------------------------------------------------
# _is_incomplete_statement – unit tests
# ---------------------------------------------------------------------------

class IsIncompleteStatementTests(unittest.TestCase):
    """Unit-level tests for the _is_incomplete_statement helper."""

    # --- Items that SHOULD be flagged (genuine headings/open fragments) ---

    def test_flags_heading_ending_in_colon(self) -> None:
        self.assertTrue(_is_incomplete_statement(
            "The applicable person categories under Section 7 are:"
        ))

    def test_flags_intro_ending_in_are(self) -> None:
        self.assertTrue(_is_incomplete_statement(
            "The conditions specified in Section 3 are"
        ))

    def test_flags_intro_ending_in_including(self) -> None:
        self.assertTrue(_is_incomplete_statement(
            "Subject matter excluded from patentability includes, including"
        ))

    def test_flags_intro_ending_in_such_as(self) -> None:
        self.assertTrue(_is_incomplete_statement(
            "Non-patentable inventions listed in Section 3 include categories such as"
        ))

    def test_flags_intro_ending_in_semicolon(self) -> None:
        self.assertTrue(_is_incomplete_statement(
            "The following shall not be considered an invention;"
        ))

    # --- Valid statutory list items that must NOT be flagged ---

    def test_does_not_flag_bullet_item_starting_with_dash(self) -> None:
        self.assertFalse(_is_incomplete_statement(
            "- An invention which is frivolous or contrary to well-established natural laws."
        ))

    def test_does_not_flag_bullet_item_starting_with_asterisk(self) -> None:
        self.assertFalse(_is_incomplete_statement(
            "* Mere discovery of a scientific principle or abstract theory."
        ))

    def test_does_not_flag_bullet_item_starting_with_number_period(self) -> None:
        self.assertFalse(_is_incomplete_statement(
            "1. A method of agriculture or horticulture."
        ))

    def test_does_not_flag_bullet_item_starting_with_number_paren(self) -> None:
        self.assertFalse(_is_incomplete_statement(
            "2) Mere admixture resulting in aggregation of properties."
        ))

    def test_does_not_flag_bullet_item_traditional_knowledge(self) -> None:
        self.assertFalse(_is_incomplete_statement(
            "- Traditional knowledge or aggregation or duplication of known properties of traditionally known component or components."
        ))

    def test_does_not_flag_bullet_item_math_method(self) -> None:
        self.assertFalse(_is_incomplete_statement(
            "- A mathematical or business method or a computer programme per se or algorithms."
        ))

    def test_does_not_flag_complete_prose_sentence(self) -> None:
        self.assertFalse(_is_incomplete_statement(
            "Section 2(1)(j) defines an invention as a new product or process involving an inventive step."
        ))

    def test_does_not_flag_sentence_containing_word_are_mid_sentence(self) -> None:
        self.assertFalse(_is_incomplete_statement(
            "The conditions are set out in Section 2(1)(j) of the Patents Act."
        ))

    def test_bullet_item_ending_in_colon_is_still_flagged(self) -> None:
        """A bullet item itself ending in ':' is a sub-heading — flag it."""
        self.assertTrue(_is_incomplete_statement(
            "- The following categories are excluded including:"
        ))


# ---------------------------------------------------------------------------
# Postprocessor — statutory list in a patentability answer
# ---------------------------------------------------------------------------

_PATENTS_ACT_SECTION3 = {
    "chunk_id": "patents-s3",
    "document_id": "india:national/patents_act_1970",
    "document_name": "The Patents Act, 1970",
    "jurisdiction": "India",
    "provision_type": "section",
    "provision_number": "3",
    "page_start": 11,
    "page_end": 14,
    "text": (
        "Section 3. What are not inventions.—The following are not inventions within the meaning of "
        "this Act,— (a) an invention which is frivolous or which claims anything obviously contrary to "
        "well established natural laws; (b) an invention the primary or intended use or commercial "
        "exploitation of which could be contrary to public order or morality; (c) the mere discovery of "
        "a scientific principle or the formulation of an abstract theory or discovery of any living thing "
        "or non-living substance occurring in nature; (d) the mere discovery of a new form of a known "
        "substance which does not result in the enhancement of the known efficacy of that substance; "
        "(p) an invention which, in effect, is traditional knowledge or which is an aggregation or "
        "duplication of known properties of traditionally known component or components."
    ),
}

_PATENTS_ACT_SECTION2 = {
    "chunk_id": "patents-s2",
    "document_id": "india:national/patents_act_1970",
    "document_name": "The Patents Act, 1970",
    "jurisdiction": "India",
    "provision_type": "section",
    "provision_number": "2",
    "page_start": 8,
    "page_end": 10,
    "text": (
        "Section 2(1)(j) 'invention' means a new product or process involving an inventive step and "
        "capable of industrial application. (ja) 'inventive step' means a feature of an invention that "
        "involves technical advance as compared to the existing knowledge or having economic significance "
        "or both and that makes the invention not obvious to a person skilled in the art. (ac) 'capable "
        "of industrial application' means that the invention is capable of being made or used in an industry."
    ),
}


class StatutoryListRetentionTests(unittest.TestCase):
    """Verify that bullet-style Section 3 items survive postprocessing."""

    def _chunks(self) -> list[dict]:
        return [_PATENTS_ACT_SECTION3, _PATENTS_ACT_SECTION2]

    def test_intro_heading_withheld_but_bullet_items_not_rejected_as_incomplete(self) -> None:
        """The introductory 'are:' line may be withheld, but each bullet must not be
        withheld solely due to incomplete_statement guard."""
        # Simulate an LLM response that puts citation only on the intro line
        # and bullet items on separate lines (the observed failure pattern).
        answer = (
            "Under Section 3, the following are not inventions: "
            "[Source: The Patents Act, 1970, section 3, pp. 11-14]\n"
            "- An invention which is frivolous or contrary to well-established natural laws.\n"
            "- Mere discovery of a scientific principle or abstract theory.\n"
            "- Traditional knowledge or its aggregation."
        )
        result = postprocess_generated_answer(
            "What are the patentability requirements?", answer, self._chunks()
        )
        # The intro line may be withheld for incomplete_statement — that is correct.
        # But bullet items must NOT be in guards as incomplete_statement.
        generated = result["claim_verification"]["generated_claims"]
        bullet_claims = [
            d for d in generated
            if d["text"].strip().startswith("-")
        ]
        for diag in bullet_claims:
            self.assertNotIn(
                "incomplete_statement", diag["safety_guards"],
                f"Bullet item wrongly flagged as incomplete_statement: {diag['text']!r}",
            )

    def test_bullet_items_missing_citation_are_withheld_as_missing_citation_not_incomplete(self) -> None:
        """Bullet items without citations are withheld for missing_citation, not incomplete_statement."""
        answer = (
            "Section 3 excludes certain subject matter. "
            "[Source: The Patents Act, 1970, section 3, pp. 11-14]\n"
            "- Mere discovery of a scientific principle."
        )
        result = postprocess_generated_answer(
            "Explain Section 3 exclusions", answer, self._chunks()
        )
        generated = result["claim_verification"]["generated_claims"]
        bullet_claims = [d for d in generated if d["text"].strip().startswith("-")]
        for diag in bullet_claims:
            # Should be withheld for missing_citation, not incomplete_statement
            self.assertNotIn("incomplete_statement", diag["safety_guards"],
                             f"Bullet incorrectly flagged incomplete: {diag['text']!r}")
            if not diag["retained"]:
                self.assertIn("missing_citation", diag["withheld_reasons"],
                              f"Expected missing_citation for uncited bullet: {diag['text']!r}")

    def test_intro_line_ending_in_colon_still_withheld(self) -> None:
        """The introductory heading ending in ':' is still correctly withheld."""
        answer = (
            "The following are not inventions under Section 3: "
            "[Source: The Patents Act, 1970, section 3, pp. 11-14]"
        )
        result = postprocess_generated_answer(
            "What are non-patentable inventions?", answer, self._chunks()
        )
        generated = result["claim_verification"]["generated_claims"]
        self.assertTrue(generated, "Expected at least one generated claim diagnostic")
        heading_diags = [
            d for d in generated
            if "incomplete_statement" in d["safety_guards"]
        ]
        self.assertTrue(
            heading_diags,
            "Expected the intro 'are:' line to be flagged as incomplete_statement",
        )

    def test_well_cited_prose_summary_of_section3_is_retained(self) -> None:
        """A prose summary of Section 3 exclusions with citation is retained."""
        answer = (
            "Section 3 of the Patents Act excludes frivolous inventions, mere discovery of "
            "scientific principles, known substance discoveries without enhanced efficacy, "
            "and traditional knowledge from patentability. "
            "[Source: The Patents Act, 1970, section 3, pp. 11-14]"
        )
        result = postprocess_generated_answer(
            "What are the patentability exclusions under Section 3?",
            answer,
            self._chunks(),
        )
        generated = result["claim_verification"]["generated_claims"]
        self.assertTrue(generated)
        self.assertTrue(
            generated[0]["retained"],
            "A well-cited prose summary of Section 3 should be retained",
        )
        self.assertNotIn("incomplete_statement", generated[0]["safety_guards"])


# ---------------------------------------------------------------------------
# Postprocessor — original diagnostics preserved on total abstention
# ---------------------------------------------------------------------------

class DiagnosticsOnTotalAbstentionTests(unittest.TestCase):
    """Claim-level diagnostics survive even when all claims are withheld."""

    def test_generated_claims_preserved_when_all_withheld(self) -> None:
        answer = (
            "Every Indian citizen needs NBA approval under Section 3. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        section3 = {
            "chunk_id": "bda-s3",
            "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002",
            "jurisdiction": "India",
            "provision_type": "section",
            "provision_number": "3",
            "page_start": 6,
            "page_end": 6,
            "text": "Section 3 lists persons requiring prior approval.",
        }
        result = postprocess_generated_answer("Explain Section 3", answer, [section3])
        self.assertEqual(result["confidence"]["decision"], "abstain")
        cv = result["claim_verification"]
        # diagnostics must survive
        self.assertIn("generated_claims", cv)
        self.assertTrue(cv["generated_claims"], "generated_claims must not be empty")
        diag = cv["generated_claims"][0]
        self.assertEqual(diag["text"], "Every Indian citizen needs NBA approval under Section 3.")
        self.assertFalse(diag["retained"])
        self.assertTrue(diag["withheld"])
        self.assertTrue(diag["withheld_reasons"])
        # original_validation must survive
        self.assertIn("original_validation", cv)
        self.assertIsNotNone(cv["original_validation"])
        self.assertEqual(cv["original_validation"]["total_citations"], 1)

    def test_rejection_reason_preserved_exactly(self) -> None:
        """The exact rejection reason key is preserved for each withheld claim."""
        answer = (
            "You are a non-resident of India so you need approval. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"
        )
        section3 = {
            "chunk_id": "bda-s3",
            "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002",
            "jurisdiction": "India",
            "provision_type": "section",
            "provision_number": "3",
            "page_start": 6,
            "page_end": 6,
            "text": "Section 3 lists persons requiring prior approval of the NBA.",
        }
        result = postprocess_generated_answer(
            "I want to collect Ashwagandha commercially.", answer, [section3]
        )
        cv = result["claim_verification"]
        self.assertIn("generated_claims", cv)
        diag = cv["generated_claims"][0]
        # Must have been withheld for unstated_user_fact (non-resident assumption)
        self.assertIn("safety_guard:unstated_user_fact", diag["withheld_reasons"])
        self.assertFalse(diag["retained"])

    def test_mixed_claim_outcome_preserves_all_diagnostics(self) -> None:
        """Retained and withheld claims both appear in generated_claims."""
        section3_chunk = {
            "chunk_id": "bda-s3",
            "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002",
            "jurisdiction": "India",
            "provision_type": "section",
            "provision_number": "3",
            "page_start": 6,
            "page_end": 6,
            "text": "Section 3 lists specified persons requiring prior approval of the National Biodiversity Authority.",
        }
        answer = (
            "Section 3 lists specified persons who need prior approval. "
            "[Source: Biological Diversity Act 2002, section 3, pp. 6-6]\n"
            "You are a non-resident of India."
        )
        result = postprocess_generated_answer(
            "Explain Section 3 BDA.", answer, [section3_chunk]
        )
        cv = result["claim_verification"]
        self.assertIn("generated_claims", cv)
        self.assertEqual(len(cv["generated_claims"]), 2)
        retained_diags = [d for d in cv["generated_claims"] if d["retained"]]
        withheld_diags = [d for d in cv["generated_claims"] if d["withheld"]]
        self.assertEqual(len(retained_diags), 1)
        self.assertEqual(len(withheld_diags), 1)
        # The withheld one must carry an explicit reason
        self.assertTrue(withheld_diags[0]["withheld_reasons"])


# ---------------------------------------------------------------------------
# Retriever — patentability query detection
# ---------------------------------------------------------------------------

class PatentabilityQueryDetectionTests(unittest.TestCase):
    """analyze_legal_query must classify patentability queries correctly."""

    def test_patentability_requirements_query_intent(self) -> None:
        result = analyze_legal_query("What are the patentability requirements?")
        # The query has 'what are' so intent should be 'definition' or 'general'
        self.assertIn(result["intent"], {"definition", "general", "prohibition"})

    def test_patentability_requirements_india_query_intent(self) -> None:
        result = analyze_legal_query(
            "What are the patentability requirements under Indian patent law?"
        )
        self.assertIn("India", result["jurisdictions_requested"])

    def test_inventive_step_query_classified(self) -> None:
        result = analyze_legal_query("What is an inventive step under the Indian Patents Act?")
        self.assertIn("India", result["jurisdictions_requested"])
        self.assertIn(result["intent"], {"definition", "general"})

    def test_novelty_inventive_step_query(self) -> None:
        result = analyze_legal_query(
            "Explain novelty, inventive step and industrial applicability under Indian patent law."
        )
        self.assertIn("India", result["jurisdictions_requested"])

    def test_non_patentable_exclusions_query_intent(self) -> None:
        result = analyze_legal_query(
            "Explain the non-patentable inventions under Section 3 of the Patents Act, 1970."
        )
        self.assertIn(result["intent"], {"explicit_provision", "prohibition"})
        # Should detect Section 3
        numbers = [p["number"] for p in result.get("explicit_provisions", [])]
        self.assertIn("3", numbers)


class PatentabilityQueryRetrievalBoostTests(unittest.TestCase):
    """LegalRetriever.retrieve must boost Sections 2, 3, 4 for patentability queries."""

    def _make_retriever_with_patent_chunks(self):
        """Return a mock LegalRetriever with minimal patent-related chunks."""
        retriever = LegalRetriever.__new__(LegalRetriever)
        patent_act_id = "india:national/patents_act_1970"
        retriever.chunks = {
            f"patent-s{n}": {
                "chunk_id": f"patents-s{n}",
                "document_id": patent_act_id,
                "document_name": "The Patents Act, 1970",
                "jurisdiction": "India",
                "provision_type": "section",
                "provision_number": str(n),
                "provision_title": f"Section {n}",
                "chapter_or_part": "",
                "subsection_path": "",
                "page_start": n * 2,
                "page_end": n * 2 + 1,
                "text": f"Section {n} content of the Patents Act.",
                "chunk_index": n,
            }
            for n in (2, 3, 4)
        }
        retriever.morphology_vocabulary = set()
        return retriever

    def test_patentability_query_boosts_sections_2_3_4(self) -> None:
        retriever = self._make_retriever_with_patent_chunks()

        def mock_dense(query, top_k=None, jurisdiction=None):
            return []

        def mock_bm25(query, top_k=None, jurisdiction=None, expansion_terms=None):
            return []

        with patch.object(LegalRetriever, "retrieve_dense", side_effect=mock_dense), \
             patch.object(LegalRetriever, "retrieve_bm25", side_effect=mock_bm25), \
             patch.dict(os.environ, {"TOP_K": "5"}, clear=False):
            result = retriever.retrieve(
                "What are the patentability requirements under Indian patent law?",
                top_k=5,
                jurisdiction="India",
            )

        # Sections 2, 3, 4 should all be present (force-added from chunk map)
        retrieved_sections = {
            str(r.get("provision_number")) for r in result
        }
        self.assertIn("2", retrieved_sections, "Section 2 must be retrieved for patentability query")
        self.assertIn("3", retrieved_sections, "Section 3 must be retrieved for patentability query")
        self.assertIn("4", retrieved_sections, "Section 4 must be retrieved for patentability query")

    def test_standalone_patentability_query_retrieves_same_as_follow_up(self) -> None:
        """A standalone and a contextual follow-up patentability question should both
        trigger patent-act boosting (the retrieval path is query-driven, not context-driven)."""
        retriever = self._make_retriever_with_patent_chunks()

        def mock_dense(query, top_k=None, jurisdiction=None):
            return []

        def mock_bm25(query, top_k=None, jurisdiction=None, expansion_terms=None):
            return []

        queries = [
            "What are the patentability requirements under Indian patent law?",
            (
                "Follow-up request: What are the patentability requirements?\n"
                "Context: Patent Act; India jurisdiction; original question: "
                "What is a patent under Indian law?; original topic: patent"
            ),
        ]
        for query in queries:
            with patch.object(LegalRetriever, "retrieve_dense", side_effect=mock_dense), \
                 patch.object(LegalRetriever, "retrieve_bm25", side_effect=mock_bm25), \
                 patch.dict(os.environ, {"TOP_K": "5"}, clear=False):
                result = retriever.retrieve(query, top_k=5, jurisdiction="India")
            retrieved_sections = {str(r.get("provision_number")) for r in result}
            self.assertIn("2", retrieved_sections,
                          f"Section 2 missing for query: {query[:60]!r}")
            self.assertIn("3", retrieved_sections,
                          f"Section 3 missing for query: {query[:60]!r}")


# ---------------------------------------------------------------------------
# Follow-up context — jurisdiction/topic continuity
# ---------------------------------------------------------------------------

class FollowUpContextRetentionTests(unittest.TestCase):
    """Verify that follow-up context is parsed without contaminating retrieval queries."""

    def test_follow_up_prefix_stripped_for_retrieval(self) -> None:
        """analyze_legal_query must handle the full follow-up payload without crashing."""
        raw_query = (
            "Follow-up request: What are the patentability requirements?\n"
            "Context: Patent Act; India jurisdiction; original question: "
            "What is a patent under Indian law?; original topic: patent"
        )
        # analyze_legal_query parses the raw string; it must not raise
        result = analyze_legal_query(raw_query)
        self.assertIsInstance(result, dict)
        self.assertIn("intent", result)

    def test_unrelated_prior_context_does_not_add_bda_expansion(self) -> None:
        """A patent follow-up must not trigger BDA expansions."""
        from app.retriever import _legal_query_expansions
        query = "What are the patentability requirements under Indian patent law?"
        expansions = _legal_query_expansions(query)
        # None of the BDA-specific terms should appear
        bda_terms = {"national biodiversity authority", "biological resources", "prior approval"}
        for term in expansions:
            self.assertNotIn(term.casefold(), bda_terms,
                             f"BDA expansion term leaked into patent query: {term!r}")

    def test_india_jurisdiction_detected_in_follow_up_payload(self) -> None:
        raw_query = (
            "Follow-up request: What are the patentability requirements?\n"
            "Context: Patent Act; India jurisdiction; original question: "
            "What is a patent under Indian law?; original topic: patent"
        )
        result = analyze_legal_query(raw_query)
        self.assertIn("India", result["jurisdictions_requested"])

    def test_follow_up_context_does_not_fabricate_explicit_provision_numbers(self) -> None:
        """The context field must not cause spurious explicit provision matches."""
        raw_query = (
            "Follow-up request: What are the patentability requirements?\n"
            "Context: Patent Act; India jurisdiction; original question: "
            "What is a patent under Indian law?; original topic: patent"
        )
        result = analyze_legal_query(raw_query)
        # The follow-up question itself does not name a specific section,
        # so explicit_provisions should be empty.
        self.assertEqual(
            result.get("explicit_provisions", []), [],
            "Follow-up question must not fabricate explicit provision references",
        )


# ---------------------------------------------------------------------------
# Bundled provisions (e.g. BDA Section 7 inside Section 6 chunk)
# ---------------------------------------------------------------------------

class BundledProvisionTests(unittest.TestCase):
    """Verify that chunks containing multiple sections validate and link properly."""

    def setUp(self) -> None:
        self.chunk_with_6_and_7 = {
            "chunk_id": "bda-chunk-6-7",
            "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002",
            "jurisdiction": "India",
            "provision_type": "section",
            "provision_number": "6",
            "page_start": 7,
            "page_end": 8,
            "text": (
                "6. Application for intellectual property rights not to be made without approval "
                "of National Biodiversity Authority.— (1) Any person or entity covered under "
                "sub-section (2) of section 3...\n"
                "3[7. Prior intimation to State Biodiversity Board for accessing biological resource "
                "for certain purposes.— (1) No person, other than the person covered under sub-section "
                "(2) of section 3, shall access any biological resource and its associated knowledge "
                "for commercial utilisation, without giving prior intimation to the concerned State "
                "Biodiversity Board.\n"
                "Provided that the provisions of this section shall not apply to the codified traditional "
                "knowledge, cultivated medicinal plants and its products, local people and communities...\n"
                "(2) In the case of cultivated medicinal plants, the exemption under sub-section (1) "
                "shall be available only if a certificate of origin is obtained from the Biodiversity "
                "Management Committee in such manner as may be prescribed.]"
            ),
        }

    def test_contained_provisions_detects_both_sections(self) -> None:
        from app.citation_validator import chunk_contained_provisions
        provisions = chunk_contained_provisions(self.chunk_with_6_and_7)
        self.assertIn("6", provisions)
        self.assertIn("7", provisions)

    def test_citation_validator_accepts_secondary_section(self) -> None:
        from app.citation_validator import validate_citations
        ans = (
            "Prior intimation is needed under Section 7. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        res = validate_citations(ans, [self.chunk_with_6_and_7])
        self.assertTrue(res["valid"])
        self.assertEqual(res["valid_citations"], 1)

    def test_explicit_provision_matches_chunk_finds_secondary_section(self) -> None:
        from app.retriever import explicit_provision_matches_chunk
        self.assertTrue(explicit_provision_matches_chunk(
            self.chunk_with_6_and_7, {"type": "section", "number": "7"}
        ))
        self.assertTrue(explicit_provision_matches_chunk(
            self.chunk_with_6_and_7, {"type": "section", "number": "6"}
        ))

    def test_build_prompt_registers_contained_provisions(self) -> None:
        from app.prompt_builder import build_prompt
        _, citation_map = build_prompt("Explain Section 7", [self.chunk_with_6_and_7])
        self.assertIn("S1", citation_map)
        contained_keys = [k for k in citation_map if "_contained_" in k and "_7" in k]
        self.assertTrue(contained_keys, "Expected secondary section 7 in citation map")
        self.assertIn("section 7", citation_map[contained_keys[0]])

    def test_insert_citation_labels_attaches_secondary_section_citation(self) -> None:
        from app.prompt_builder import build_prompt, insert_citation_labels
        _, citation_map = build_prompt("Explain Section 7", [self.chunk_with_6_and_7])
        raw_text = (
            "Section 7 requires prior intimation to the State Biodiversity Board "
            "for commercial utilisation."
        )
        labeled = insert_citation_labels(raw_text, citation_map)
        self.assertIn("[Source: Biological Diversity Act 2002, section 7, pp. 7-8]", labeled)

    def test_postprocessor_retains_secondary_section_claim(self) -> None:
        ans = (
            "Section 7 requires prior intimation to the State Biodiversity Board "
            "for accessing biological resources for commercial utilisation, other than for "
            "persons covered under section 3(2) and subject to stated exceptions. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        res = postprocess_generated_answer(
            "What permissions apply under BDA?", ans, [self.chunk_with_6_and_7]
        )
        self.assertEqual(res["confidence"]["decision"], "answer")
        self.assertIn("Section 7 requires prior intimation", res["answer"])
        self.assertEqual(res["claim_verification"]["withheld_claim_count"], 0)

    def test_postprocessor_retains_commercial_utilisation_section7_claim(self) -> None:
        """Section 7 prior intimation for commercial utilisation is recognized as a valid statutory statement."""
        ans = (
            "Under Section 7, prior intimation to the State Biodiversity Board is required "
            "for accessing biological resources for commercial utilisation. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        res = postprocess_generated_answer(
            "What permissions apply under BDA?", ans, [self.chunk_with_6_and_7]
        )
        diag = res["claim_verification"]["generated_claims"][0]
        self.assertNotIn("bda_section7_scope", diag.get("safety_guards", []))
        self.assertTrue(diag["retained"], f"Expected claim to be retained: {diag}")

    def test_postprocessor_retains_certificate_of_origin_obtained_from_bmc(self) -> None:
        """Claim stating certificate of origin is obtained from BMC is valid and not misattributed."""
        ans = (
            "The Act provides an exemption for cultivated medicinal plants if a certificate of origin "
            "is obtained from the Biodiversity Management Committee. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        res = postprocess_generated_answer(
            "What permissions apply under BDA?", ans, [self.chunk_with_6_and_7]
        )
        diag = res["claim_verification"]["generated_claims"][0]
        self.assertNotIn("bda_section7_misattributes_bmc_certificate", diag.get("safety_guards", []))
        self.assertTrue(diag["retained"], f"Expected claim to be retained: {diag}")

    def test_insert_citation_labels_attaches_s7_for_certificate_of_origin(self) -> None:
        """insert_citation_labels links certificate of origin to Section 7 when section number is omitted."""
        from app.prompt_builder import build_prompt, insert_citation_labels
        _, citation_map = build_prompt("What permissions apply?", [self.chunk_with_6_and_7])
        raw_text = (
            "An exemption applies if a certificate of origin is obtained from the Biodiversity Management Committee."
        )
        labeled = insert_citation_labels(raw_text, citation_map)
        self.assertIn("[Source: Biological Diversity Act 2002, section 7, pp. 7-8]", labeled)

    def test_withholds_misattributed_bmc_plant_source_when_no_certificate(self) -> None:
        """Claim saying plants themselves must be obtained from BMC is correctly withheld."""
        ans = (
            "Under Section 7, cultivated medicinal plants must be obtained from the "
            "Biodiversity Management Committee. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        res = postprocess_generated_answer(
            "What permissions apply under BDA?", ans, [self.chunk_with_6_and_7]
        )
        diag = res["claim_verification"]["generated_claims"][0]
        self.assertIn("bda_section7_misattributes_bmc_certificate", diag.get("safety_guards", []))
        self.assertFalse(diag["retained"])

    def test_format_retained_claim_prose_resolves_dangling_this_section(self) -> None:
        """Dangling 'This section' is replaced with the cited section name and spaces are normalized."""
        from app.answer_postprocessor import _format_retained_claim_prose
        claim = {
            "text": "This section applies to non-resident Indians and foreign companies   .",
            "citations": ["[Source: Biological Diversity Act 2002, section 3, pp. 6-6]"],
        }
        formatted = _format_retained_claim_prose(claim)
        self.assertTrue(formatted.startswith("Section 3 applies to non-resident Indians and foreign companies."))
        self.assertNotIn("   .", formatted)
        self.assertIn("[Source: Biological Diversity Act 2002, section 3, pp. 6-6]", formatted)

    def test_withholds_unrelated_repository_provisions_for_access_queries(self) -> None:
        """Administrative repository and voucher specimen rules are withheld for commercial access queries."""
        chunk_s39 = {
            "chunk_id": "bda-s39",
            "document_id": "india:national/biological_diversity_act_2002",
            "document_name": "Biological Diversity Act 2002",
            "jurisdiction": "India",
            "provision_type": "section",
            "provision_number": "39",
            "page_start": 18,
            "page_end": 18,
            "text": "The repositories shall keep in safe custody the biological material, including voucher specimens.",
        }
        ans = (
            "The repositories shall keep in safe custody the biological material, including voucher specimens. "
            "[Source: Biological Diversity Act 2002, section 39, pp. 18-18]"
        )
        res = postprocess_generated_answer(
            "What permissions and legal requirements apply to purchase cultivated Ashwagandha roots?",
            ans,
            [chunk_s39],
        )
        diag = res["claim_verification"]["generated_claims"][0]
        self.assertIn("unrelated_administrative_provision", diag.get("safety_guards", []))
        self.assertFalse(diag["retained"])

    def test_withholds_cultivated_exemption_applied_to_wild_forest_query(self) -> None:
        """Cultivated plant exemption is withheld when applied to a wild forest collection query."""
        wild_query = (
            "I want to collect Ashwagandha plants from a forest in Karnataka and use them to "
            "prepare a herbal product for commercial sale. What permissions apply?"
        )
        ans = (
            "Cultivated medicinal plants, including Ashwagandha, are exempt if a certificate of origin "
            "is obtained from the BMC. [Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        res = postprocess_generated_answer(wild_query, ans, [self.chunk_with_6_and_7])
        diag = res["claim_verification"]["generated_claims"][0]
        self.assertIn("wild_forest_cultivated_misapplication", diag.get("safety_guards", []))
        self.assertFalse(diag["retained"])

    def test_withholds_invented_bmc_registration_for_wild_forest_collection(self) -> None:
        """Invented BMC registration requirement for wild forest collection is withheld."""
        wild_query = (
            "I want to collect Ashwagandha plants from a forest in Karnataka for commercial sale."
        )
        ans = (
            "The collector must register with the BMC to obtain legal permissions. "
            "[Source: Biological Diversity Act 2002, section 7, pp. 7-8]"
        )
        res = postprocess_generated_answer(wild_query, ans, [self.chunk_with_6_and_7])
        diag = res["claim_verification"]["generated_claims"][0]
        self.assertIn("wild_forest_bmc_registration_invention", diag.get("safety_guards", []))
        self.assertFalse(diag["retained"])


if __name__ == "__main__":
    unittest.main()

