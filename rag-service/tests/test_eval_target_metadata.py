"""Validate Stage 6A expected target metadata against the selected candidate chunk map."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from tests.evaluate_full_retrieval import matches_target  # noqa: E402

EVAL_PATH = Path(__file__).with_name("eval_set.json")
CANDIDATE_CHUNKS_PATH = (
    RAG_ROOT / "staging" / "chunk-refresh-regulation-20261031T140000Z-audit"
    / "chunks.candidate.json"
)
MATCH_FIELDS = (
    "document_id", "document_name", "jurisdiction", "provision_type", "provision_number",
)


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


class CandidateEvaluationTargetTests(unittest.TestCase):
    def test_every_expected_target_matches_candidate_chunk_metadata(self) -> None:
        dataset = json.loads(EVAL_PATH.read_text(encoding="utf-8-sig"))
        candidate = json.loads(CANDIDATE_CHUNKS_PATH.read_text(encoding="utf-8-sig"))
        self.assertIsInstance(dataset, dict)
        self.assertIsInstance(dataset.get("items"), list)
        self.assertIsInstance(candidate, dict)
        self.assertIsInstance(candidate.get("chunks"), list)
        chunks = candidate["chunks"]
        self.assertTrue(chunks, "candidate chunk map contains no chunks")
        unmatched: list[str] = []

        for item in dataset["items"]:
            item_id = item.get("id", "<missing evaluation id>")
            targets = item.get("expected_targets")
            if not isinstance(targets, list):
                unmatched.append(f"{item_id}: expected_targets is not a list")
                continue
            for target_index, target in enumerate(targets, start=1):
                if not isinstance(target, dict):
                    unmatched.append(f"{item_id} target {target_index}: target is not an object")
                    continue
                missing = [field for field in MATCH_FIELDS if field not in target]
                if missing:
                    unmatched.append(f"{item_id} target {target_index}: missing fields {missing}")
                    continue
                if any(matches_target(chunk, target) for chunk in chunks if isinstance(chunk, dict)):
                    continue

                nearby = [chunk for chunk in chunks if isinstance(chunk, dict)
                          and _normalized(chunk.get("document_id")) == _normalized(target.get("document_id"))
                          and _normalized(chunk.get("provision_number")) == _normalized(target.get("provision_number"))]
                if not nearby:
                    unmatched.append(
                        f"{item_id} target {target_index}: no candidate record for "
                        f"document_id={target.get('document_id')!r}, "
                        f"provision_number={target.get('provision_number')!r}; "
                        f"unmatched fields={list(MATCH_FIELDS)}"
                    )
                    continue
                mismatches = {}
                for field in MATCH_FIELDS:
                    found = sorted({str(chunk.get(field) or "") for chunk in nearby})
                    if not any(_normalized(value) == _normalized(target.get(field)) for value in found):
                        mismatches[field] = {"expected": target.get(field), "candidate_values": found}
                unmatched.append(f"{item_id} target {target_index}: mismatched fields={mismatches}")

        self.assertFalse(unmatched, "Unmatched candidate evaluation targets:\n" + "\n".join(unmatched))


if __name__ == "__main__":
    unittest.main()
