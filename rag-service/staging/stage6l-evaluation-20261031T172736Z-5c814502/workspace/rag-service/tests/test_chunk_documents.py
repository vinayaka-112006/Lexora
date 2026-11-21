"""Regression tests for headings found in the extracted legal corpus."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_prep.chunk_documents import process_documents


RAG_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_PATH = RAG_ROOT / "data" / "extracted_documents.json"


class ChunkDocumentHeadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        documents = json.loads(EXTRACTED_PATH.read_text(encoding="utf-8-sig"))
        cls.documents = {document["document_id"]: document for document in documents}

    def _chunks_for(self, document_id: str) -> list[dict[str, object]]:
        output, _ = process_documents([self.documents[document_id]])
        return output["chunks"]

    def test_biological_diversity_section_7_footnote_heading_is_its_own_chunk(self) -> None:
        chunks = self._chunks_for("india:national/biological_diversity_act_2002")
        section_7 = [chunk for chunk in chunks if chunk.get("provision_number") == "7"]

        self.assertEqual(len(section_7), 1)
        chunk = section_7[0]
        self.assertEqual(chunk["document_id"], "india:national/biological_diversity_act_2002")
        self.assertEqual(chunk["document_name"], "Biological Diversity Act 2002")
        self.assertEqual(chunk["filename"], "biological_diversity_act_2002.pdf")
        self.assertEqual(chunk["provision_type"], "section")
        self.assertEqual(
            chunk["provision_title"],
            "Prior intimation to State Biodiversity Board for accessing biological resource for certain purposes",
        )
        self.assertEqual((chunk["page_start"], chunk["page_end"]), (7, 8))
        self.assertIn("3[7.", chunk["text"])
        self.assertIn("the concerned State Biodiversity Board", chunk["text"])

    def test_drugs_act_multi_letter_sections_are_separate_chunks(self) -> None:
        chunks = self._chunks_for("india:national/drugs_cosmetics_act")
        by_number = {
            str(chunk.get("provision_number")): chunk
            for chunk in chunks
            if chunk.get("provision_number") in {"33E", "33EEB", "33EEC"}
        }

        self.assertEqual(set(by_number), {"33E", "33EEB", "33EEC"})
        expected = {
            "33EEB": ("Regulation of manufacture for sale of Ayurvedic, Siddha and Unani drugs", (33, 33)),
            "33EEC": ("Prohibition of manufacture and sale of certain Ayurvedic, Siddha and Unani drugs", (33, 34)),
        }
        for number, (title, pages) in expected.items():
            chunk = by_number[number]
            self.assertEqual(chunk["document_id"], "india:national/drugs_cosmetics_act")
            self.assertEqual(chunk["document_name"], "Drugs Cosmetics Act")
            self.assertEqual(chunk["filename"], "drugs_cosmetics_act.pdf")
            self.assertEqual(chunk["provision_type"], "section")
            self.assertEqual(chunk["provision_title"], title)
            self.assertEqual((chunk["page_start"], chunk["page_end"]), pages)
            self.assertIn(f"{number}.", chunk["text"])

        self.assertNotIn("33EEB. Regulation of manufacture", by_number["33E"]["text"])
        self.assertNotIn("33EEC. Prohibition of manufacture", by_number["33E"]["text"])

    def test_drugs_act_first_schedule_entries_are_not_statutory_sections(self) -> None:
        chunks = self._chunks_for("india:national/drugs_cosmetics_act")
        schedule_entries = [
            chunk for chunk in chunks
            if chunk.get("provision_number") in {"60", "72", "80"}
        ]

        self.assertEqual(schedule_entries, [])

        output, _ = process_documents([self.documents["india:national/drugs_cosmetics_act"]])
        first_schedule = [
            page for page in output["contents_pages"]
            if page.get("page_type") == "schedule" and page.get("page_number") == 42
        ]
        self.assertEqual(len(first_schedule), 1)
        self.assertIn("THE FIRST SCHEDULE", first_schedule[0]["text"])
        self.assertIn("60. Agasthiyar Paripuranam", first_schedule[0]["text"])
        second_schedule_page = [
            page for page in output["contents_pages"]
            if page.get("page_type") == "schedule" and page.get("page_number") == 43
        ]
        self.assertEqual(len(second_schedule_page), 1)
        self.assertIn("72. Yogi Vatha Kaviyam", second_schedule_page[0]["text"])

    def test_fssai_body_provisions_are_regulations_and_schedules_stay_untyped(self) -> None:
        chunks = self._chunks_for("india:national/fssai_ayurveda_aahara_regulations_2022")
        body_regulations = [chunk for chunk in chunks if chunk.get("content_type") == "provision"]
        self.assertTrue(body_regulations)
        self.assertTrue(all(chunk.get("provision_type") == "regulation" for chunk in body_regulations))
        self.assertTrue(any(
            chunk.get("provision_number") == "2"
            and chunk.get("page_start") == 15
            and str(chunk.get("provision_title", "")).startswith("Definitions")
            for chunk in body_regulations
        ))

        schedule_chunks = [
            chunk for chunk in chunks
            if chunk.get("content_type") == "schedule"
            and (4 <= chunk.get("page_start", 0) <= 14 or 18 <= chunk.get("page_start", 0) <= 27)
        ]
        self.assertTrue(schedule_chunks)
        self.assertTrue(all(chunk.get("provision_type") is None
                            and chunk.get("provision_number") is None
                            for chunk in schedule_chunks))
        output, _ = process_documents([self.documents["india:national/fssai_ayurveda_aahara_regulations_2022"]])
        contents_pages = {
            page["page_number"] for page in output["contents_pages"]
            if page.get("page_type") == "contents"
        }
        self.assertNotIn(3, contents_pages)
        hindi_regulation_12 = [
            chunk for chunk in chunks
            if chunk.get("provision_number") == "12" and chunk.get("page_start") == 3
        ]
        self.assertEqual(len(hindi_regulation_12), 1)
        self.assertEqual(hindi_regulation_12[0]["provision_type"], "regulation")
        self.assertEqual(hindi_regulation_12[0]["page_end"], 3)

    def test_patent_rules_contents_continuation_does_not_start_schedule_early(self) -> None:
        output, _ = process_documents([self.documents["india:national/patent-rules-2024"]])
        contents_page_numbers = {
            page["page_number"] for page in output["contents_pages"]
            if page.get("page_type") == "contents"
        }
        schedule_page_numbers = {
            page["page_number"] for page in output["contents_pages"]
            if page.get("page_type") == "schedule"
        }

        self.assertTrue(set(range(1, 7)).issubset(contents_page_numbers))
        self.assertNotIn(6, schedule_page_numbers)
        self.assertIn(76, schedule_page_numbers)

    def test_patent_rules_body_headings_get_rule_metadata_and_wrapped_title(self) -> None:
        output, _ = process_documents([self.documents["india:national/patent-rules-2024"]])
        rules = {
            str(chunk.get("provision_number")): chunk
            for chunk in output["chunks"] if chunk.get("provision_type") == "rule"
        }
        self.assertTrue({"1", "82", "133"}.issubset(rules))
        expected = {
            "1": ("Short title and commencement", (7, 7)),
            "82": ("Preparation of amended specifications, etc", (52, 52)),
            "133": ("Supply of certified copies and certificates under sections 72 and 147", (73, 73)),
        }
        for number, (title, pages) in expected.items():
            chunk = rules[number]
            self.assertEqual(chunk["document_id"], "india:national/patent-rules-2024")
            self.assertEqual(chunk["document_name"], "Patent Rules 2024")
            self.assertEqual(chunk["provision_title"], title)
            self.assertEqual((chunk["page_start"], chunk["page_end"]), pages)

        # Lowercase references in Rule 24/Rule 37 body text remain ordinary text.
        lowercase_references = [
            chunk for chunk in output["chunks"]
            if "rule 20." in chunk["text"] or "rule 37." in chunk["text"]
        ]
        self.assertTrue(lowercase_references)
        self.assertTrue(all(chunk["provision_type"] == "rule" for chunk in lowercase_references))
        self.assertTrue(all(chunk["provision_number"] != "20" for chunk in lowercase_references))

        contents_pages = {
            page["page_number"] for page in output["contents_pages"]
            if page["page_type"] == "contents"
        }
        schedule_pages = {
            page["page_number"] for page in output["contents_pages"]
            if page["page_type"] == "schedule"
        }
        self.assertTrue(set(range(1, 7)).issubset(contents_pages))
        self.assertTrue({76, 77, 98}.issubset(schedule_pages))
        self.assertFalse(any(
            chunk["provision_type"] == "rule"
            and chunk["page_start"] in contents_pages | schedule_pages
            for chunk in output["chunks"]
        ))

    def test_front_matter_stays_general_before_first_provision(self) -> None:
        cases = (
            ("india:national/drugs_cosmetics_act", "section", "1", 6),
            ("india:national/drugs_magic_remedies_act", "section", "1", 4),
            ("international:international/pct", "article", "1", 7),
        )
        for document_id, provision_type, number, first_page in cases:
            with self.subTest(document_id=document_id):
                output, _ = process_documents([self.documents[document_id]])
                first = next(chunk for chunk in output["chunks"]
                             if chunk.get("provision_type") == provision_type
                             and str(chunk.get("provision_number")) == number
                             and chunk.get("provision_chunk_index") == 0)
                self.assertEqual(first["page_start"], first_page)
                self.assertEqual(first["source_pages"][0], first_page)
                self.assertEqual(first["page_end"], max(first["source_pages"]))
                self.assertTrue(any(chunk.get("content_type") == "general"
                                    and chunk.get("page_start") == 1
                                    for chunk in output["chunks"]))
                contents = {page["page_number"] for page in output["contents_pages"]
                            if page.get("page_type") == "contents"}
                self.assertFalse(any(first["page_start"] <= page <= first["page_end"]
                                     for page in contents))

    def test_biodiversity_convention_front_matter_and_print_footer_are_general(self) -> None:
        output, _ = process_documents([self.documents["international:international/cbd"]])
        chunks = output["chunks"]
        article_one = next(chunk for chunk in chunks
                           if chunk.get("provision_type") == "article"
                           and str(chunk.get("provision_number")) == "1"
                           and chunk.get("provision_chunk_index") == 0)
        self.assertEqual(article_one["page_start"], 8)
        self.assertEqual(article_one["source_pages"][0], 8)
        self.assertNotIn("Convention\non\nBiologiCal Diversity", article_one["text"])
        article_six = [chunk for chunk in chunks
                       if chunk.get("provision_type") == "article"
                       and str(chunk.get("provision_number")) == "6"
                       and chunk.get("page_start") == 34]
        self.assertTrue(article_six)
        self.assertTrue(any("disagreement as to whether the conciliation commission" in chunk["text"]
                            for chunk in article_six))
        self.assertTrue(all("Printed on 100% recycled paper" not in chunk["text"]
                            and chunk["page_end"] == 34 for chunk in article_six))
        footer = [chunk for chunk in chunks if chunk.get("content_type") == "general"
                  and "Printed on 100% recycled paper" in chunk["text"]]
        self.assertEqual(len(footer), 1)
        self.assertEqual(footer[0]["source_pages"], [36])
        self.assertIn("Printed in iCao, Canada", footer[0]["text"])
        self.assertIn("july 2011", footer[0]["text"])

    def test_chapter_context_ignores_body_sentence_and_keeps_real_wrapped_heading(self) -> None:
        chunks = self._chunks_for("india:national/drugs_cosmetics_act")
        section_33c = next(chunk for chunk in chunks
                           if chunk.get("provision_number") == "33C")
        self.assertIn("and to carry out the other functions assigned to it by this Chapter",
                      section_33c["text"])
        expected_chapter = "CHAPTER IVA PROVISIONS RELATING TO 4[AYURVEDIC, SIDDHA AND UNANI ] DRUGS"
        for number in ("33EEB", "33EEC"):
            chunk = next(item for item in chunks if item.get("provision_number") == number)
            self.assertEqual(chunk["chapter_or_part"], expected_chapter)

    def test_drugs_magic_remedies_schedule_list_is_not_parsed_as_sections(self) -> None:
        output, _ = process_documents([self.documents["india:national/drugs_magic_remedies_act"]])
        schedule_page_numbers = {
            page["page_number"] for page in output["contents_pages"]
            if page.get("page_type") == "schedule"
        }
        schedule_provisions = [
            chunk for chunk in output["chunks"]
            if chunk.get("provision_type") == "section"
            and chunk.get("page_start", 0) in schedule_page_numbers
        ]

        self.assertTrue({9, 10, 11}.issubset(schedule_page_numbers))
        self.assertEqual(schedule_provisions, [])
        self.assertTrue(any(
            chunk.get("provision_number") == "16" and chunk.get("page_start") == 7
            for chunk in output["chunks"]
        ))


if __name__ == "__main__":
    unittest.main()
