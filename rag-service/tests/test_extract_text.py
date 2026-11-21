"""Regression tests for source-title consistency during PDF extraction."""
from __future__ import annotations

import unittest
from pathlib import Path

from pypdf import PdfReader

from data_prep.extract_text import CORPUS_ROOT, document_display_name, readable_name


class DocumentDisplayNameTests(unittest.TestCase):
    def test_patents_act_uses_its_verified_title_page_name(self) -> None:
        pdf_path = CORPUS_ROOT / "national" / "patent_act_2024.pdf"
        title_page = PdfReader(str(pdf_path)).pages[0].extract_text() or ""

        self.assertIn("THE PATENTS ACT, 1970", title_page)
        self.assertEqual(document_display_name(pdf_path), "The Patents Act, 1970")

    def test_unmapped_pdf_names_keep_existing_filename_fallback(self) -> None:
        self.assertEqual(document_display_name(CORPUS_ROOT / "national" / "sample_rules_2024.pdf"),
                         "Sample Rules 2024")
        self.assertEqual(readable_name("sample_rules_2024.pdf"), "Sample Rules 2024")


if __name__ == "__main__":
    unittest.main()
