"""Tests for paired Chroma and chunk-map configuration without real index access."""
from __future__ import annotations

import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

RAG_ROOT = Path(__file__).resolve().parents[1]
for entry in (RAG_ROOT, RAG_ROOT / "data_prep"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from chroma_config import (  # noqa: E402
    DEFAULT_CHROMA_PATH,
    DEFAULT_CHUNKS_PATH,
    PROJECT_ROOT,
    resolve_chroma_path,
    resolve_chunks_path,
    resolve_index_paths,
)
from app import api, main as cli_main, retriever  # noqa: E402


class ChromaPathConfigTests(unittest.TestCase):
    def _sample_chunk(self, document_id="candidate:act", index=8):
        return {
            "document_id": document_id,
            "document_name": "Candidate Act",
            "jurisdiction": "India",
            "chunk_id": f"{document_id}#chunk-{index:04d}",
            "chunk_index": index,
            "text": "Candidate chunk text",
            "provision_type": "section",
            "provision_number": "7",
        }

    def _write_map(self, path, records):
        path.write_text(json.dumps({"chunks": records}), encoding="utf-8")
        return path

    def _mocked_clients(self, stored_ids=()):
        client = Mock()
        collection = Mock()
        collection.get.return_value = {"ids": list(stored_ids)}
        client.get_collection.return_value = collection
        return client, (
            patch("sentence_transformers.SentenceTransformer", return_value=Mock()),
            patch("chromadb.PersistentClient", return_value=client),
        )

    def _make_retriever(self, path):
        rows = json.loads(path.read_text(encoding="utf-8"))["chunks"]
        identifiers = [retriever._stable_chunk_id(row) for row in rows]
        client, patches = self._mocked_clients(identifiers)
        with patch.dict(os.environ, {"CHROMA_PATH": str(path.parent / "index"), "CHUNKS_PATH": str(path)}), \
             patches[0], patches[1]:
            instance = retriever.LegalRetriever()
        return instance, client

    def test_both_unset_preserves_production_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_chroma_path(), PROJECT_ROOT / "rag-service" / "chroma_db")
            self.assertEqual(resolve_chunks_path(), PROJECT_ROOT / "rag-service" / "data" / "chunks.json")
            self.assertEqual(resolve_index_paths(), (DEFAULT_CHROMA_PATH, DEFAULT_CHUNKS_PATH, False))

    def test_custom_absolute_paths_resolve_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            chroma, chunks = Path(directory) / "chroma", Path(directory) / "chunks.json"
            with patch.dict(os.environ, {"CHROMA_PATH": str(chroma), "CHUNKS_PATH": str(chunks)}):
                self.assertEqual(resolve_chroma_path(), chroma)
                self.assertEqual(resolve_chunks_path(), chunks)
                self.assertEqual(resolve_index_paths(), (chroma, chunks, True))

    def test_custom_relative_paths_resolve_from_project_root(self):
        with patch.dict(os.environ, {"CHROMA_PATH": "indexes/candidate", "CHUNKS_PATH": "staging/candidate.json"}):
            self.assertEqual(resolve_chroma_path(), (PROJECT_ROOT / "indexes/candidate").resolve())
            self.assertEqual(resolve_chunks_path(), (PROJECT_ROOT / "staging/candidate.json").resolve())
            self.assertEqual(
                resolve_index_paths(),
                ((PROJECT_ROOT / "indexes/candidate").resolve(),
                 (PROJECT_ROOT / "staging/candidate.json").resolve(), True),
            )

    def test_partial_pair_configuration_fails_before_chroma_initialization(self):
        client, patches = self._mocked_clients()
        with patch.dict(os.environ, {"CHROMA_PATH": "configured-index"}, clear=True), patches[0], patches[1]:
            with self.assertRaisesRegex(ValueError, "must be configured together"):
                retriever.LegalRetriever()
        client.get_collection.assert_not_called()

    def test_configured_index_and_chunk_map_id_mismatch_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_map(Path(directory) / "candidate.json", [self._sample_chunk()])
            client, patches = self._mocked_clients(["id-not-in-map"])
            with patch.dict(os.environ, {"CHROMA_PATH": str(Path(directory) / "index"), "CHUNKS_PATH": str(path)}), \
                 patches[0], patches[1]:
                with self.assertRaisesRegex(RuntimeError, "do not match"):
                    retriever.LegalRetriever()
            client.get_collection.return_value.get.assert_called_once_with(include=[])

    def test_retriever_loads_configured_map_and_filters_by_its_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self._sample_chunk()
            path = self._write_map(Path(directory) / "candidate.json", [row])
            chroma = Path(directory) / "index"
            client, patches = self._mocked_clients([retriever._stable_chunk_id(row)])
            with patch.dict(os.environ, {"CHUNKS_PATH": str(path), "CHROMA_PATH": str(chroma)}), patches[0], patches[1]:
                instance = retriever.LegalRetriever()
            identifier = retriever._stable_chunk_id(row)
            self.assertIn(identifier, instance.chunks)
            self.assertEqual(instance.chunks[identifier]["document_name"], "Candidate Act")
            self.assertTrue(instance._eligible(identifier, "India"))
            self.assertFalse(instance._eligible("absent-id", "India"))
            self.assertFalse(chroma.exists())
            client.get_collection.assert_called_once_with(name="ip_sakti_legal")
            client.get_collection.return_value.get.assert_called_once_with(include=[])

    def test_candidate_only_id_is_eligible_when_candidate_map_is_configured(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self._sample_chunk("india:national/patent-rules-2024", 86)
            path = self._write_map(Path(directory) / "candidate.json", [row])
            instance, _ = self._make_retriever(path)
            self.assertTrue(instance._eligible(retriever._stable_chunk_id(row), "India"))
            absent = self._sample_chunk("old:canonical-only", 1)
            self.assertFalse(instance._eligible(retriever._stable_chunk_id(absent), "India"))

    def test_missing_chunk_map_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "Chunk map was not found"):
                retriever.load_chunk_map(Path(directory) / "missing.json")

    def test_malformed_json_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Malformed chunk-map JSON"):
                retriever.load_chunk_map(path)

    def test_invalid_chunk_map_shapes_fail_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            cases = (
                ([], "object containing a 'chunks' list"),
                ({"chunks": []}, "contains no chunks"),
                ({"chunks": [None]}, "is not an object"),
                ({"chunks": [{"text": "missing identity"}]}, "needs document_id and chunk_index"),
                ({"chunks": [{"document_id": "x", "chunk_index": 1, "text": " "}]}, "no usable text"),
            )
            for payload, message in cases:
                with self.subTest(message=message):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        retriever.load_chunk_map(path)

    def test_duplicate_stable_or_source_chunk_ids_fail_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            row = self._sample_chunk()
            self._write_map(path, [row, dict(row)])
            with self.assertRaisesRegex(ValueError, "Duplicate document_id/chunk_index identity"):
                retriever.load_chunk_map(path)
            second = self._sample_chunk("candidate:other", 9)
            second["chunk_id"] = row["chunk_id"]
            self._write_map(path, [row, second])
            with self.assertRaisesRegex(ValueError, "Duplicate chunk_id"):
                retriever.load_chunk_map(path)

    def test_api_uses_both_configured_paths_without_opening_real_database(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self._sample_chunk()
            path = self._write_map(Path(directory) / "api-candidate.json", [row])
            chroma = Path(directory) / "api-index"
            client, patches = self._mocked_clients([retriever._stable_chunk_id(row)])
            with patch.dict(os.environ, {"CHROMA_PATH": str(chroma), "CHUNKS_PATH": str(path)}), \
                 patch.object(api, "_retriever_cache", None), patches[0], patches[1]:
                instance = api._get_shared_retriever()
            self.assertIn(retriever._stable_chunk_id(row), instance.chunks)
            client.get_collection.assert_called_once_with(name="ip_sakti_legal")
            client.get_collection.return_value.get.assert_called_once_with(include=[])
            self.assertFalse(chroma.exists())

    def test_cli_uses_both_configured_paths_without_opening_real_database(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self._sample_chunk()
            path = self._write_map(Path(directory) / "cli-candidate.json", [row])
            chroma = Path(directory) / "cli-index"
            client, patches = self._mocked_clients([retriever._stable_chunk_id(row)])
            constructed = []
            def construct_retriever(*args, **kwargs):
                instance = retriever.LegalRetriever(*args, **kwargs)
                constructed.append(instance)
                return instance
            with patch.dict(os.environ, {"CHROMA_PATH": str(chroma), "CHUNKS_PATH": str(path)}), \
                 patch.object(cli_main, "LegalRetriever", side_effect=construct_retriever), \
                 patch.object(cli_main, "OllamaClient", return_value=Mock()), \
                 patch("builtins.input", return_value="exit"), \
                 redirect_stdout(io.StringIO()), patches[0], patches[1]:
                cli_main.main()
            self.assertEqual(len(constructed), 1)
            self.assertIn(retriever._stable_chunk_id(row), constructed[0].chunks)
            client.get_collection.assert_called_once_with(name="ip_sakti_legal")
            client.get_collection.return_value.get.assert_called_once_with(include=[])
            self.assertFalse(chroma.exists())

    def test_index_builder_uses_same_pair_and_keeps_unset_defaults(self):
        builder = importlib.import_module("build_index")
        with patch.dict(os.environ, {"CHROMA_PATH": "build-index", "CHUNKS_PATH": "build-chunks.json"}):
            importlib.reload(builder)
            self.assertEqual(builder.PERSIST_PATH, (PROJECT_ROOT / "build-index").resolve())
            self.assertEqual(builder.INPUT_PATH, (PROJECT_ROOT / "build-chunks.json").resolve())
        with patch.dict(os.environ, {}, clear=True):
            importlib.reload(builder)
            self.assertEqual(builder.PERSIST_PATH, DEFAULT_CHROMA_PATH)
            self.assertEqual(builder.INPUT_PATH, DEFAULT_CHUNKS_PATH)


if __name__ == "__main__":
    unittest.main()
