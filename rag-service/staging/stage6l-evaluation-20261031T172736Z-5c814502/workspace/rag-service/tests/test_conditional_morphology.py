"""Unit tests for the reversible, conditional query morphology layer."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.query_morphology import conditionally_expand_query, expand_query_morphology  # noqa: E402
from app.retriever import LegalRetriever, analyze_legal_query  # noqa: E402


class ConditionalMorphologyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query = "How do trademarks protect creators rights?"
        self.vocabulary = {"trademark", "trademarks", "protect", "protects", "creator", "creators", "right", "rights"}

    def test_normal_query_receives_morphology(self) -> None:
        analysis = analyze_legal_query(self.query)
        expanded, applied = conditionally_expand_query(
            self.query, analysis["intent"], analysis["explicit_provision"], self.vocabulary, True)
        self.assertTrue(applied)
        self.assertEqual(expanded, self.query + " trademark protects creator right")

    def test_explicit_section_query_is_not_expanded(self) -> None:
        query = "What does Section 3 of the Patents Act say?"
        analysis = analyze_legal_query(query)
        expanded, applied = conditionally_expand_query(
            query, analysis["intent"], analysis["explicit_provision"], self.vocabulary, True)
        self.assertFalse(applied)
        self.assertEqual(expanded, query)

    def test_explicit_article_query_is_not_expanded(self) -> None:
        query = "What does Article 6 of the Nagoya Protocol require?"
        analysis = analyze_legal_query(query)
        expanded, applied = conditionally_expand_query(
            query, analysis["intent"], analysis["explicit_provision"], self.vocabulary, True)
        self.assertFalse(applied)
        self.assertEqual(expanded, query)

    def test_comparison_query_is_not_expanded(self) -> None:
        query = "Compare Indian patent requirements with international rules."
        analysis = analyze_legal_query(query)
        self.assertEqual(analysis["intent"], "comparison")
        expanded, applied = conditionally_expand_query(
            query, analysis["intent"], analysis["explicit_provision"], self.vocabulary, True)
        self.assertFalse(applied)
        self.assertEqual(expanded, query)

    def test_relation_wording_in_comparison_query_is_not_expanded(self) -> None:
        query = "How do Indian approval rules relate to Nagoya Protocol concepts?"
        analysis = analyze_legal_query(query)
        self.assertEqual(analysis["intent"], "general")
        expanded, applied = conditionally_expand_query(
            query, analysis["intent"], analysis["explicit_provision"], self.vocabulary, True)
        self.assertFalse(applied)
        self.assertEqual(expanded, query)

    def test_short_query_is_not_expanded(self) -> None:
        query = "What is a trademark?"
        analysis = analyze_legal_query(query)
        expanded, applied = conditionally_expand_query(
            query, analysis["intent"], analysis["explicit_provision"], self.vocabulary, True)
        self.assertFalse(applied)
        self.assertEqual(expanded, query)

    def test_three_meaningful_tokens_are_too_short(self) -> None:
        query = "What is purpose Nagoya Protocol?"
        analysis = analyze_legal_query(query)
        expanded, applied = conditionally_expand_query(
            query, analysis["intent"], analysis["explicit_provision"], self.vocabulary, True)
        self.assertFalse(applied)
        self.assertEqual(expanded, query)

    def test_expansion_is_deterministic(self) -> None:
        first = expand_query_morphology(self.query, self.vocabulary)
        second = expand_query_morphology(self.query, self.vocabulary)
        self.assertEqual(first, second)

    def test_original_query_is_preserved(self) -> None:
        original = self.query
        expanded = expand_query_morphology(original, self.vocabulary)
        self.assertEqual(original, "How do trademarks protect creators rights?")
        self.assertNotEqual(expanded, original)

    def _fake_retriever(self, *provisions: tuple[str, str, str]) -> tuple[LegalRetriever, list[dict[str, object]]]:
        retriever = LegalRetriever.__new__(LegalRetriever)
        retriever.morphology_vocabulary = self.vocabulary
        chunks: dict[str, dict[str, object]] = {}
        rows: list[dict[str, object]] = []
        for index, (identifier, jurisdiction, number) in enumerate(provisions):
            chunk: dict[str, object] = {
                "chunk_id": identifier, "text": "Meaning of the provision.",
                "document_id": identifier, "document_name": "Example Act",
                "jurisdiction": jurisdiction, "provision_type": "section",
                "provision_number": number, "provision_title": "Definitions",
                "chapter_or_part": "", "subsection_path": [], "page_start": 1,
                "page_end": 1, "source_pages": [1], "extraction_methods": ["pypdf"],
                "content_type": "provision", "chunk_index": index,
            }
            chunks[identifier] = chunk
            rows.append({**chunk, "dense_rank": index + 1, "bm25_rank": index + 1,
                         "distance": 0.1 + index, "bm25_score": 1.0})
        retriever.chunks = chunks
        retriever.chunk_ids = list(chunks)
        return retriever, rows

    def test_expanded_query_is_passed_to_dense_and_bm25(self) -> None:
        retriever, rows = self._fake_retriever(("india-1", "India", "1"))
        with patch.dict(os.environ, {"MORPHOLOGY_EXPANSION_ENABLED": "true"}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows) as dense, \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows) as bm25:
            result = retriever.retrieve(self.query, top_k=1, jurisdiction="India")
        expected = expand_query_morphology(self.query, self.vocabulary)
        self.assertEqual(dense.call_args.args[0], expected)
        self.assertEqual(bm25.call_args.args[0], expected)
        self.assertEqual(result[0]["original_query"], self.query)
        self.assertEqual(result[0]["retrieval_query"], expected)
        self.assertTrue(result[0]["morphology_applied"])
        self.assertEqual(retriever.last_retrieval_debug["original_query"], self.query)

    def test_disabled_flag_preserves_original_retrieval_query(self) -> None:
        retriever, rows = self._fake_retriever(("india-1", "India", "1"))
        with patch.dict(os.environ, {"MORPHOLOGY_EXPANSION_ENABLED": "false"}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows) as dense, \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows) as bm25:
            retriever.retrieve(self.query, top_k=1, jurisdiction="India")
        self.assertEqual(dense.call_args.args[0], self.query)
        self.assertEqual(bm25.call_args.args[0], self.query)

    def test_existing_explicit_provision_bonus_still_works(self) -> None:
        retriever, rows = self._fake_retriever(("patent-83", "India", "83"))
        with patch.dict(os.environ, {"MORPHOLOGY_EXPANSION_ENABLED": "true"}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            result = retriever.retrieve("What does Section 83 of the Patents Act say?", top_k=1, jurisdiction="India")
        self.assertEqual(result[0]["provision_number"], "83")
        self.assertGreater(result[0]["explicit_provision_bonus"], 0)
        self.assertFalse(result[0]["morphology_applied"])

    def test_explicit_section_three_is_identified_correctly(self) -> None:
        retriever, rows = self._fake_retriever(("patent-3", "India", "3"))
        with patch.dict(os.environ, {"MORPHOLOGY_EXPANSION_ENABLED": "true"}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            result = retriever.retrieve("What does Section 3 of the Patents Act say?", top_k=1, jurisdiction="India")
        self.assertEqual(result[0]["provision_number"], "3")
        self.assertEqual(result[0]["explicit_provision_bonus"], 0.05)
        self.assertFalse(result[0]["morphology_applied"])

    def test_existing_jurisdiction_filter_is_preserved(self) -> None:
        retriever, rows = self._fake_retriever(("india-1", "India", "1"), ("intl-2", "International", "2"))
        def filtered_rows(*_args: object, jurisdiction: str, **_kwargs: object) -> list[dict[str, object]]:
            return [row for row in rows if row["jurisdiction"] == jurisdiction]
        with patch.dict(os.environ, {"MORPHOLOGY_EXPANSION_ENABLED": "true"}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", side_effect=filtered_rows) as dense, \
             patch.object(LegalRetriever, "retrieve_bm25", side_effect=filtered_rows) as bm25:
            result = retriever.retrieve(self.query, top_k=5, jurisdiction="India")
        self.assertTrue(result)
        self.assertTrue(all(row["jurisdiction"] == "India" for row in result))
        self.assertEqual(dense.call_args.kwargs["jurisdiction"], "India")
        self.assertEqual(bm25.call_args.kwargs["jurisdiction"], "India")

    def test_existing_comparison_handling_is_preserved(self) -> None:
        retriever, rows = self._fake_retriever(("india-1", "India", "1"), ("intl-2", "International", "2"))
        query = "Compare Indian and international patent requirements."
        with patch.dict(os.environ, {"MORPHOLOGY_EXPANSION_ENABLED": "true"}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            result = retriever.retrieve(query, top_k=2, jurisdiction="all")
        self.assertEqual(retriever.last_retrieval_debug["retrieval_query"], query)
        self.assertFalse(retriever.last_retrieval_debug["morphology_applied"])
        self.assertEqual({row["jurisdiction"] for row in result}, {"India", "International"})

    def test_fusion_does_not_duplicate_candidates_from_both_retrievers(self) -> None:
        retriever, rows = self._fake_retriever(("india-1", "India", "1"))
        with patch.dict(os.environ, {"MORPHOLOGY_EXPANSION_ENABLED": "true"}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            result = retriever.retrieve(self.query, top_k=5, jurisdiction="India")
        result_ids = [row["chunk_id"] for row in result]
        self.assertEqual(len(result_ids), len(set(result_ids)))


if __name__ == "__main__":
    unittest.main()
