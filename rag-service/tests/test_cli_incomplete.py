"""CLI regression checks for incomplete model responses."""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app import main
from app.llm_client import IncompleteGenerationError


class _Retriever:
    def retrieve(self, _query: str, _top_k: int):
        return [{
            "chunk_id": "patent-section-2", "text": "A patent means a patent for an invention.",
            "document_id": "india:national/patents_act_1970", "document_name": "The Patents Act, 1970",
            "jurisdiction": "India", "provision_type": "section", "provision_number": "2",
            "page_start": 8, "page_end": 10,
            "hybrid_score": 0.03, "final_score": 0.03, "dense_rank": 1, "bm25_rank": 1,
            "intent_bonus": 0.0, "query_intent": "general",
            "source_pages": [8, 9, 10], "extraction_methods": ["pypdf"],
            "content_type": "provision", "provision_title": "Definitions",
        }]


class CliIncompleteResponseTests(unittest.TestCase):
    def test_cli_withholds_partial_unverified_text(self) -> None:
        incomplete = IncompleteGenerationError("The statute provides that")
        incomplete.partial_answer = "The statute provides that [Source: The Patents Act, 1970, section 2, pp. 8-10]"
        output = io.StringIO()
        with (
            patch.object(main, "_generate_grounded_answer", side_effect=incomplete),
            contextlib.redirect_stdout(output),
        ):
            main._handle_question("Explain the patent definition.", _Retriever(), object(), 5)

        displayed = output.getvalue()
        self.assertIn("INCOMPLETE RESPONSE", displayed)
        self.assertIn("partial model output was withheld", displayed)
        self.assertNotIn("The statute provides that", displayed)


if __name__ == "__main__":
    unittest.main()
