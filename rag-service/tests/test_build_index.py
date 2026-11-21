"""Focused tests for Chroma-bound text preparation in the index builder."""
from __future__ import annotations

import copy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

RAG_ROOT = Path(__file__).resolve().parents[1]
DATA_PREP = RAG_ROOT / "data_prep"
if str(DATA_PREP) not in sys.path:
    sys.path.insert(0, str(DATA_PREP))

import build_index  # noqa: E402


class FakeVectors:
    def __init__(self, count: int):
        self.count = count

    def tolist(self):
        return [[0.25, 0.75] for _ in range(self.count)]


class FakeModel:
    def __init__(self):
        self.inputs = []

    def encode(self, texts, **kwargs):
        self.inputs.append(list(texts))
        return FakeVectors(len(texts))


class FakeCollection:
    def __init__(self):
        self.records = {}
        self.upserts = []

    def get(self, include=None):
        return {"ids": list(self.records)}

    def delete(self, ids):
        for identifier in ids:
            self.records.pop(identifier, None)

    def upsert(self, *, ids, embeddings, documents, metadatas):
        payload = {"ids": list(ids), "embeddings": embeddings, "documents": list(documents), "metadatas": list(metadatas)}
        self.upserts.append(payload)
        for identifier, document, metadata in zip(ids, documents, metadatas):
            self.records[identifier] = (document, metadata)

    def count(self):
        return len(self.records)


class BuildIndexSanitizationTests(unittest.TestCase):
    def _run_index(self, chunks, batch_size):
        model = FakeModel()
        client = Mock()
        collection = FakeCollection()
        sentence_transformers = types.ModuleType("sentence_transformers")
        sentence_transformers.SentenceTransformer = Mock(return_value=model)
        chromadb = types.ModuleType("chromadb")
        chromadb.PersistentClient = Mock(return_value=client)
        persist_path = Mock()
        with patch.dict(sys.modules, {"sentence_transformers": sentence_transformers, "chromadb": chromadb}), \
             patch.object(build_index, "_open_collection", return_value=(client, collection)), \
             patch.object(build_index, "_remove_stale_records") as remove_stale, \
             patch("builtins.print"):
            returned, embedded = build_index.index_chunks(chunks, "test-model", batch_size, persist_path=persist_path)
        persist_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        remove_stale.assert_called_once_with(collection, {build_index.stable_chunk_id(row) for row in chunks})
        self.assertIs(returned[0], model)
        self.assertIs(returned[1], collection)
        self.assertEqual(embedded, len(chunks))
        return model, collection

    def _chunk(self, index, text):
        return {
            "document_id": "india:national/test-act",
            "document_name": "Test Act",
            "filename": "test-act.pdf",
            "jurisdiction": "India",
            "provision_type": "section",
            "provision_number": str(index + 1),
            "provision_title": "Text preservation",
            "chapter_or_part": "Part I",
            "subsection_path": [],
            "page_start": index + 1,
            "page_end": index + 1,
            "source_pages": [index + 1],
            "extraction_methods": ["fixture"],
            "chunk_index": index,
            "provision_chunk_index": 0,
            "content_type": "provision",
            "text": text,
        }

    def test_nul_removed_identically_for_embedding_and_document_without_mutating_chunk(self):
        original = "  first\t  line\n\u0927\u093e\u0930\u093e\u200d \x00 punctuation: [x]!  "
        chunk = self._chunk(0, original)
        before = copy.deepcopy(chunk)
        expected = original.replace("\x00", "")

        model, collection = self._run_index([chunk], batch_size=4)

        self.assertEqual(model.inputs, [[expected]])
        self.assertEqual(collection.upserts[0]["documents"], [expected])
        self.assertEqual(collection.upserts[0]["metadatas"], [build_index.chunk_metadata(before)])
        self.assertEqual(collection.upserts[0]["ids"], [build_index.stable_chunk_id(before)])
        self.assertEqual(chunk, before)

    def test_text_without_nul_passes_through_exactly(self):
        text = "line one\t  line two\n\u0927\u093e\u0930\u093e\u200d"
        model, collection = self._run_index([self._chunk(0, text)], batch_size=1)
        self.assertEqual(model.inputs, [[text]])
        self.assertEqual(collection.upserts[0]["documents"], [text])

    def test_batch_order_and_existing_indexing_behavior_are_preserved(self):
        chunks = [self._chunk(0, "A\x00  "), self._chunk(1, "B\n"), self._chunk(2, "\u0927\u093e\u0930\u093e C\x00")]
        model, collection = self._run_index(chunks, batch_size=2)
        expected_text = [row["text"].replace("\x00", "") for row in chunks]
        expected_ids = [build_index.stable_chunk_id(row) for row in chunks]

        self.assertEqual(model.inputs, [expected_text[:2], expected_text[2:]])
        self.assertEqual([row for batch in collection.upserts for row in batch["documents"]], expected_text)
        self.assertEqual([row for batch in collection.upserts for row in batch["ids"]], expected_ids)
        self.assertEqual([row for batch in collection.upserts for row in batch["metadatas"]], [build_index.chunk_metadata(row) for row in chunks])
        self.assertEqual(collection.count(), 3)


if __name__ == "__main__":
    unittest.main()
