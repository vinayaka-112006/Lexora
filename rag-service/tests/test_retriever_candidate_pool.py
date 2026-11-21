"""Focused tests for the configurable pre-fusion candidate pool."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.retriever import LegalRetriever, _legal_query_expansions, analyze_legal_query  # noqa: E402


class CandidatePoolTests(unittest.TestCase):
    def _candidate_rows(self, count: int) -> list[dict[str, object]]:
        return [
            {"chunk_id": f"chunk-{rank}", "text": "matching text", "document_id": "doc",
             "document_name": "Example Act", "jurisdiction": "India", "provision_type": "section",
             "provision_number": str(rank), "provision_title": "", "dense_rank": rank,
             "bm25_rank": rank, "hybrid_score": None}
            for rank in range(1, count + 1)
        ]

    def test_default_pool_is_wider_than_final_count(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        rows = self._candidate_rows(20)
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows) as dense, \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows) as bm25:
            result = retriever.retrieve("Explain general legal provisions", top_k=3, jurisdiction="India")
        self.assertEqual(dense.call_args.kwargs["top_k"], 20)
        self.assertEqual(bm25.call_args.kwargs["top_k"], 20)
        self.assertEqual(dense.call_args.kwargs["jurisdiction"], "India")
        self.assertEqual(bm25.call_args.kwargs["jurisdiction"], "India")
        self.assertEqual(len(result), 3)

    def test_canonical_extracted_title_overrides_stale_chroma_label(self) -> None:
        class Vector(list):
            def tolist(self):
                return list(self)

        retriever = LegalRetriever.__new__(LegalRetriever)
        retriever.chunks = {
            "patent-2": {"document_id": "india:national/patent_act_2024",
                         "document_name": "The Patents Act, 1970", "filename": "patent_act_2024.pdf",
                         "jurisdiction": "India", "text": "Section 2", "provision_type": "section",
                         "provision_number": "2", "page_start": 8, "page_end": 10}
        }
        retriever.model = type("Model", (), {"encode": lambda *_args, **_kwargs: [Vector([0.1])]})()
        retriever.collection = type("Collection", (), {
            "count": lambda _self: 1,
            "query": lambda _self, **_kwargs: {
                "ids": [["patent-2"]], "documents": [["Section 2"]],
                "metadatas": [[{"document_name": "Patent Act 2024", "jurisdiction": "India",
                                "provision_type": "section", "provision_number": "2",
                                "page_start": 8, "page_end": 10}]],
                "distances": [[0.1]],
            },
        })()
        result = retriever.retrieve_dense("patent", jurisdiction="India")
        self.assertEqual(result[0]["document_name"], "The Patents Act, 1970")

    def test_pool_is_at_least_final_count_and_configurable(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        rows = self._candidate_rows(25)
        with patch.dict(os.environ, {"RETRIEVAL_CANDIDATE_K": "12"}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows) as dense, \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows) as bm25:
            result = retriever.retrieve("Explain general legal provisions", top_k=25, jurisdiction="all")
        self.assertEqual(dense.call_args.kwargs["top_k"], 25)
        self.assertEqual(bm25.call_args.kwargs["top_k"], 25)
        self.assertEqual(len(result), 25)

    def test_existing_dense_and_bm25_environment_overrides_remain_supported(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        rows = self._candidate_rows(24)
        env = {"RETRIEVAL_CANDIDATE_K": "20", "DENSE_TOP_K": "24", "BM25_TOP_K": "17"}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows) as dense, \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows) as bm25:
            retriever.retrieve("Explain general legal provisions", top_k=5)
        self.assertEqual(dense.call_args.kwargs["top_k"], 24)
        self.assertEqual(bm25.call_args.kwargs["top_k"], 17)

    def test_exact_patent_queries_infer_india_and_keep_follow_up_context(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        rows = self._candidate_rows(3)
        retriever.chunks = {row["chunk_id"]: dict(row) for row in rows}
        queries = (
            "What is a patent under Indian law?",
            "Follow-up request: How does this apply to Ayurvedic products?\n\n"
            "Context: Patent Act, Indian law. The original question concerns a patent under Indian law?",
        )
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows) as dense, \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            for query in queries:
                retriever.retrieve(query, top_k=3)
                self.assertEqual(dense.call_args.kwargs["jurisdiction"], "India")

    def test_patent_definition_prioritizes_act_definition_and_patentability_sections(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        patent_id = "india:national/patent_act_2024"
        retriever.chunks = {}
        for number, title, text in (
            ("2", "Definitions and interpretation", "(m) patent means a patent for any invention granted under this Act."),
            ("3", "What are not inventions", "The following are not inventions within the meaning of this Act."),
            ("4", "Inventions relating to atomic energy not patentable", "No patent shall be granted for specified inventions."),
        ):
            chunk_id = f"patent-{number}"
            retriever.chunks[chunk_id] = {
                "chunk_id": chunk_id, "document_id": patent_id, "document_name": "The Patents Act, 1970",
                "jurisdiction": "India", "provision_type": "section", "provision_number": number,
                "provision_title": title, "text": text,
            }
        retriever.chunks["design-definition"] = {
            "chunk_id": "design-definition", "document_id": "india:designs_act",
            "document_name": "Designs Act", "jurisdiction": "India", "provision_type": "section",
            "provision_number": "2", "provision_title": "Definitions", "text": "Design means ...",
        }
        rows = self._candidate_rows(1)
        rows[0].update({"document_id": "india:designs_act", "document_name": "Designs Act",
                        "provision_number": "2", "provision_title": "Definitions"})
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            results = retriever.retrieve("What is a patent under Indian law?", top_k=3)
        self.assertEqual([str(row["provision_number"]) for row in results], ["2", "3", "4"])
        self.assertTrue(all(row["document_id"] == patent_id for row in results))

    def test_ayurvedic_patent_follow_up_prioritizes_existing_definition_and_exclusions(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        patent_id = "india:national/patent_act_2024"
        retriever.chunks = {
            "patent-2": {"chunk_id": "patent-2", "document_id": patent_id,
                         "document_name": "The Patents Act, 1970", "jurisdiction": "India",
                         "provision_type": "section", "provision_number": "2",
                         "provision_title": "Definitions and interpretation",
                         "text": "Invention means a new product or process involving an inventive step and capable of industrial application."},
            "patent-3": {"chunk_id": "patent-3", "document_id": patent_id,
                         "document_name": "The Patents Act, 1970", "jurisdiction": "India",
                         "provision_type": "section", "provision_number": "3",
                         "provision_title": "What are not inventions",
                         "text": "An invention which is traditional knowledge or duplicates known properties of traditionally known components is excluded."},
            "design-2": {"chunk_id": "design-2", "document_id": "india:designs_act",
                          "document_name": "Designs Act", "jurisdiction": "India",
                          "provision_type": "section", "provision_number": "2",
                          "provision_title": "Definitions", "text": "Design means ..."},
        }
        design = dict(retriever.chunks["design-2"], dense_rank=1, bm25_rank=1, hybrid_score=None)
        query = ("Follow-up request: How does this apply to Ayurvedic products?\n\n"
                 "Context: Patent Act; India jurisdiction; original topic: patent")
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=[design]), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=[design]) as bm25:
            results = retriever.retrieve(query, top_k=3)
        self.assertEqual([row["chunk_id"] for row in results[:2]], ["patent-3", "patent-2"])
        self.assertEqual(len(results), 2)
        self.assertEqual({str(row["provision_number"]) for row in results}, {"2", "3"})
        expansions = bm25.call_args.kwargs["expansion_terms"]
        self.assertIn("traditional knowledge", expansions)
        self.assertIn("inventive step", expansions)

    def test_explicit_act_reference_scopes_provision_bonus_to_named_document(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        patent = self._candidate_rows(1)[0]
        patent.update({"chunk_id": "patent-3", "document_id": "india:patent_act",
                       "document_name": "Patent Act", "provision_number": "3"})
        designs = dict(patent, chunk_id="designs-3", document_id="india:designs_act",
                       document_name="Designs Act")
        retriever.chunks = {row["chunk_id"]: dict(row) for row in (patent, designs)}
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=[patent, designs]), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=[patent, designs]):
            results = retriever.retrieve("What does Patent Act Section 3 say?", top_k=2, jurisdiction="India")
        scores = {row["document_name"]: row["explicit_provision_bonus"] for row in results}
        self.assertEqual(scores, {"Patent Act": 0.05, "Designs Act": 0.0})

    def test_explicit_rule_queries_are_analyzed_and_scoped_to_rule_metadata(self) -> None:
        queries = (
            ("What does Rule 1 of the Patent Rules provide?", "1"),
            ("Explain Rule 82.", "82"),
            ("What does Rule 133 say?", "133"),
        )
        for query, number in queries:
            analysis = analyze_legal_query(query)
            self.assertEqual(analysis["intent"], "explicit_provision")
            self.assertEqual(analysis["explicit_provision"], {"type": "rule", "number": number})

        retriever = LegalRetriever.__new__(LegalRetriever)
        expected = {
            "rule-1": {"chunk_id": "rule-1", "document_id": "india:national/patent-rules-2024",
                       "document_name": "Patent Rules 2024", "jurisdiction": "India",
                       "provision_type": "rule", "provision_number": "1",
                       "page_start": 7, "page_end": 7, "text": "Rule 1. Short title and commencement"},
            "rule-82": {"chunk_id": "rule-82", "document_id": "india:national/patent-rules-2024",
                        "document_name": "Patent Rules 2024", "jurisdiction": "India",
                        "provision_type": "rule", "provision_number": "82",
                        "page_start": 52, "page_end": 52, "text": "Rule 82. Preparation of amended specifications"},
            "rule-133": {"chunk_id": "rule-133", "document_id": "india:national/patent-rules-2024",
                         "document_name": "Patent Rules 2024", "jurisdiction": "India",
                         "provision_type": "rule", "provision_number": "133",
                         "page_start": 73, "page_end": 73, "text": "Rule 133. Supply of certified copies"},
        }
        unrelated = {"chunk_id": "section-82", "document_id": "india:other-act",
                     "document_name": "Other Act", "jurisdiction": "India",
                     "provision_type": "section", "provision_number": "82",
                     "page_start": 1, "page_end": 1, "text": "Section 82"}
        retriever.chunks = {**expected, "section-82": unrelated}
        rows = self._candidate_rows(1)
        rows[0].update({"chunk_id": "generic", "document_id": "other",
                        "document_name": "Other Act", "provision_number": "2"})
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            for query, number in queries:
                results = retriever.retrieve(query, top_k=3, jurisdiction="India")
                matching = [row for row in results if row.get("provision_type") == "rule"]
                self.assertEqual([row["chunk_id"] for row in matching], [f"rule-{number}"])
                self.assertEqual(matching[0]["explicit_provision_bonus"], 0.05)
                self.assertEqual(matching[0]["jurisdiction"], "India")

    def test_explicit_section_and_article_analysis_is_unchanged(self) -> None:
        self.assertEqual(
            analyze_legal_query("Explain Section 33EEB")["explicit_provision"],
            {"type": "section", "number": "33eeb"},
        )
        self.assertEqual(
            analyze_legal_query("Explain Article 6")["explicit_provision"],
            {"type": "article", "number": "6"},
        )

    def test_multiple_explicit_sections_are_prioritized_in_the_named_act(self) -> None:
        query = "Explain the difference between Section 3 and Section 7 of the Biological Diversity Act."
        analysis = analyze_legal_query(query)
        self.assertEqual(analysis["explicit_provisions"], [
            {"type": "section", "number": "3"},
            {"type": "section", "number": "7"},
        ])
        retriever = LegalRetriever.__new__(LegalRetriever)
        targets = [
            {"chunk_id": f"section-{number}", "document_id": "india:national/biological_diversity_act_2002",
             "document_name": "Biological Diversity Act, 2002", "jurisdiction": "India",
             "provision_type": "section", "provision_number": number, "page_start": page,
             "page_end": page, "text": f"Section {number} body text."}
            for number, page in (("3", 4), ("7", 8))
        ]
        retriever.chunks = {row["chunk_id"]: row for row in targets}
        unrelated = self._candidate_rows(1)
        unrelated[0].update({"chunk_id": "unrelated", "document_id": "india:other_act",
                             "document_name": "Other Act", "jurisdiction": "India"})
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=unrelated), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=unrelated):
            results = retriever.retrieve(query, top_k=2, jurisdiction="India")
        self.assertEqual({row["chunk_id"] for row in results}, {"section-3", "section-7"})
        self.assertTrue(all(row["explicit_provision_bonus"] == 0.05 for row in results))

    def test_coordinated_provision_lists_extract_each_number_without_capturing_years(self) -> None:
        cases = (
            ("Explain Sections 3 and 7 of the Biological Diversity Act, 2002.", ["3", "7"]),
            ("Compare Sections 3, 4, 6 and 7 of the Biological Diversity Act, 2002.", ["3", "4", "6", "7"]),
            ("Explain Section 3 and Section 7 of the Biological Diversity Act, 2002.", ["3", "7"]),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(
                    [item["number"] for item in analyze_legal_query(query)["explicit_provisions"]],
                    expected,
                )
        self.assertEqual(
            analyze_legal_query("Explain Sections 3 and 7 of the 2002 Act.")["explicit_provisions"],
            [{"type": "section", "number": "3"}, {"type": "section", "number": "7"}],
        )

    def test_explicit_provision_diagnostic_reports_each_requested_section(self) -> None:
        from app.retriever import explicit_provision_diagnostic

        source = "india:national/biological_diversity_act_2002"
        catalog = {
            "s3": {"chunk_id": "s3", "document_id": source,
                   "document_name": "Biological Diversity Act, 2002", "jurisdiction": "India",
                   "provision_type": "section", "provision_number": "3", "text": "Section 3 text"},
            "s7": {"chunk_id": "s7", "document_id": source,
                   "document_name": "Biological Diversity Act, 2002", "jurisdiction": "India",
                   "provision_type": "section", "provision_number": "7", "text": "Section 7 text"},
        }
        diagnostic = explicit_provision_diagnostic(
            "Explain Sections 3 and 7 of the Biological Diversity Act, 2002.",
            [catalog["s3"]], catalog,
        )
        self.assertEqual([item["number"] for item in diagnostic["requested"]], ["3", "7"])
        self.assertEqual([item["number"] for item in diagnostic["missing"]], ["7"])
        self.assertEqual(diagnostic["requested"][0]["chunk_ids"], ["s3"])

    def test_explicit_subsections_match_their_parent_section_only_when_text_contains_clause(self) -> None:
        query = "Explain Section 3(d) and Section 3(p) of the Patents Act."
        analysis = analyze_legal_query(query)
        self.assertEqual(analysis["explicit_provisions"], [
            {"type": "section", "number": "3(d)"},
            {"type": "section", "number": "3(p)"},
        ])
        retriever = LegalRetriever.__new__(LegalRetriever)
        section3 = {
            "chunk_id": "section-3", "document_id": "india:national/patents_act_1970",
            "document_name": "The Patents Act, 1970", "jurisdiction": "India",
            "provision_type": "section", "provision_number": "3", "page_start": 11,
            "page_end": 12, "text": "(d) known substances. (p) traditional knowledge.",
        }
        retriever.chunks = {"section-3": section3}
        rows = self._candidate_rows(1)
        rows[0].update({"chunk_id": "unrelated", "document_id": "india:other",
                        "document_name": "Other Act", "jurisdiction": "India"})
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            results = retriever.retrieve(query, top_k=1, jurisdiction="India")
        self.assertEqual([row["chunk_id"] for row in results], ["section-3"])
        self.assertEqual(results[0]["explicit_provision_bonus"], 0.05)

    def test_explicit_regulation_queries_are_analyzed_and_scoped_to_regulation_metadata(self) -> None:
        queries = (
            "Regulation 2",
            "Regulation 2 of the Ayurveda Aahara Regulations",
        )
        for query in queries:
            analysis = analyze_legal_query(query)
            self.assertEqual(analysis["intent"], "explicit_provision")
            self.assertEqual(analysis["explicit_provision"], {"type": "regulation", "number": "2"})

        retriever = LegalRetriever.__new__(LegalRetriever)
        target = {
            "chunk_id": "fssai-regulation-2", "document_id": "india:national/fssai_ayurveda_aahara_regulations_2022",
            "document_name": "FSSAI Ayurveda Aahara Regulations 2022", "jurisdiction": "India",
            "provision_type": "regulation", "provision_number": "2",
            "page_start": 15, "page_end": 15, "text": "Regulation 2. Definitions.",
        }
        unrelated = dict(target, chunk_id="other-section-2", document_id="india:other",
                          document_name="Other Act", provision_type="section")
        retriever.chunks = {target["chunk_id"]: target, unrelated["chunk_id"]: unrelated}
        rows = self._candidate_rows(1)
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows), \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows):
            results = retriever.retrieve(
                "Regulation 2 of the Ayurveda Aahara Regulations", top_k=3, jurisdiction="India"
            )
        matching = [row for row in results if row.get("provision_type") == "regulation"]
        self.assertEqual([row["chunk_id"] for row in matching], ["fssai-regulation-2"])
        self.assertEqual(matching[0]["explicit_provision_bonus"], 0.05)

    def test_explicit_rule_retrieval_keeps_both_jurisdiction_filters(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        retriever.chunks = {}
        rows = self._candidate_rows(1)
        for jurisdiction in ("India", "International"):
            rows[0]["jurisdiction"] = jurisdiction
            with patch.dict(os.environ, {}, clear=True), \
                 patch.object(LegalRetriever, "retrieve_dense", return_value=rows) as dense, \
                 patch.object(LegalRetriever, "retrieve_bm25", return_value=rows) as bm25:
                retriever.retrieve("Explain Rule 82", top_k=1, jurisdiction=jurisdiction)
            self.assertEqual(dense.call_args.kwargs["jurisdiction"], jurisdiction)
            self.assertEqual(bm25.call_args.kwargs["jurisdiction"], jurisdiction)

    def test_corpus_attested_legal_wording_expands_lexical_candidates(self) -> None:
        cases = (
            ("What grounds could prevent registration of a proposed brand name as a trademark?",
             {"shall not be registered", "devoid of distinctive character"}),
            ("Compare India's exclusions from patentability with TRIPS rules.",
             {"not inventions", "not patentable"}),
            ("What is the effect of an international patent application under the PCT?",
             {"effects of the international application"}),
            ("How do approval rules for biological resources relate to Nagoya?",
             {"prior approval", "National Biodiversity Authority", "application for intellectual property rights"}),
            ("Compare access and benefit-sharing concepts under Nagoya.",
             {"fair and equitable sharing", "fair and equitable benefit-sharing", "mutually agreed terms",
              "benefits arising from utilization of genetic resources"}),
            ("Compare protection criteria for geographical indications with TRIPS.",
             {"shall not be registered", "deceive or cause confusion"}),
            ("How does India's design protection framework compare internationally?",
             {"not new or original", "significantly distinguishable"}),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertTrue(expected.issubset(set(_legal_query_expansions(query))))

    def test_legal_expansions_are_passed_only_to_bm25_without_changing_query(self) -> None:
        retriever = LegalRetriever.__new__(LegalRetriever)
        retriever.chunks = {}
        rows = self._candidate_rows(1)
        query = "Compare India's exclusions from patentability with TRIPS rules."
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(LegalRetriever, "retrieve_dense", return_value=rows) as dense, \
             patch.object(LegalRetriever, "retrieve_bm25", return_value=rows) as bm25:
            retriever.retrieve(query, top_k=1, jurisdiction="all")
        self.assertEqual(dense.call_args.args[0], query)
        self.assertEqual(bm25.call_args.args[0], query)
        self.assertIn("not inventions", bm25.call_args.kwargs["expansion_terms"])
        self.assertIn("not patentable", bm25.call_args.kwargs["expansion_terms"])


if __name__ == "__main__":
    unittest.main()
