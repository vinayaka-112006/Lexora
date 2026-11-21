"""Focused regression tests for mark-specific definition retrieval signals."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.retriever import LegalRetriever, analyze_legal_query  # noqa: E402


def _row(
    chunk_id: str, title: str, text: str, number: str = "2", document_id: str | None = None,
    document_name: str = "Example Act",
) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "document_id": document_id or chunk_id,
        "document_name": document_name,
        "jurisdiction": "India",
        "provision_type": "section",
        "provision_number": number,
        "provision_title": title,
        "dense_rank": None,
        "bm25_rank": 1,
    }


class DefinitionMarkRelevanceTests(unittest.TestCase):
    def _retrieve(self, query: str, row: dict[str, object]):
        retriever = LegalRetriever.__new__(LegalRetriever)
        retriever.chunks = {}
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=[]), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=[row]) as bm25:
            results = retriever.retrieve(query, top_k=1, jurisdiction="India")
        return results[0], bm25.call_args.kwargs["expansion_terms"]

    def test_patent_definition_does_not_get_generic_mark_expansion_or_bonus(self) -> None:
        query = "What is a patent under Indian law?"
        row, expansions = self._retrieve(
            query, _row("trade-mark-definition", "Trade marks", "A mark identifies goods.")
        )
        self.assertNotIn("mark", expansions)
        self.assertNotIn("mark", analyze_legal_query(query)["keywords"])
        self.assertEqual(row["intent_bonus"], 0.0)

    def test_trademark_definition_retains_mark_expansion_and_relevant_bonus(self) -> None:
        query = "What is a trademark under Indian law?"
        row, expansions = self._retrieve(
            query, _row("trademark-definition", "Trade marks", "A sign identifies goods.")
        )
        self.assertIn("mark", expansions)
        self.assertIn("mark", analyze_legal_query(query)["keywords"])
        self.assertEqual(row["intent_bonus"], 0.005)

    def test_explicit_patent_section_keeps_reference_bonus_without_mark_bonus(self) -> None:
        query = "What does Section 2 of the Patents Act say under Indian law?"
        patent = _row("patent-section-2", "Definitions and interpretation", "Patent definitions.",
                      document_id="india:national/patent_act_2024", document_name="Patent Act 2024")
        designs = _row("designs-section-2", "Definitions", "Design definitions.",
                       document_id="india:national/designs_act", document_name="Designs Act")
        retriever = LegalRetriever.__new__(LegalRetriever)
        retriever.chunks = {patent["chunk_id"]: patent, designs["chunk_id"]: designs}
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=[]), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=[designs]) as bm25:
            results = retriever.retrieve(query, top_k=2, jurisdiction="India")

        self.assertEqual(bm25.call_args.kwargs["expansion_terms"], ())
        self.assertEqual(results[0]["document_id"], "india:national/patent_act_2024")
        self.assertEqual(results[0]["query_intent"], "explicit_provision")
        self.assertEqual(results[0]["intent_bonus"], 0.0)
        self.assertEqual(results[0]["explicit_provision_bonus"], 0.05)
        self.assertEqual(results[1]["document_id"], "india:national/designs_act")
        self.assertEqual(results[1]["explicit_provision_bonus"], 0.0)

    def test_general_patent_query_does_not_scope_candidates_to_an_act(self) -> None:
        query = "What is a patent under Indian law?"
        patent = _row("patent-definition", "Definitions", "Patent definitions.",
                      document_id="india:national/patent_act_2024", document_name="Patent Act 2024")
        designs = _row("design-definition", "Definitions", "Design definitions.",
                       document_id="india:national/designs_act", document_name="Designs Act")
        dense = [dict(patent, dense_rank=1), dict(designs, dense_rank=2)]
        lexical = [dict(patent, bm25_rank=1), dict(designs, bm25_rank=2)]
        retriever = LegalRetriever.__new__(LegalRetriever)
        retriever.chunks = {patent["chunk_id"]: patent, designs["chunk_id"]: designs}
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=dense), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=lexical):
            results = retriever.retrieve(query, top_k=5, jurisdiction="India")

        self.assertEqual({row["document_id"] for row in results}, {
            "india:national/patent_act_2024", "india:national/designs_act",
        })
        self.assertTrue(all(row["explicit_provision_bonus"] == 0.0 for row in results))


if __name__ == "__main__":
    unittest.main()
