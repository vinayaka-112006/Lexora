"""Validate Stage 6K holdout queries against chunks and the existing Chroma index."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
PROJECT_ROOT = RAG_ROOT.parent
HOLDOUT_PATH = TESTS_DIR / "holdout_eval_set.json"
CHUNKS_PATH = RAG_ROOT / "data" / "chunks.json"
EVAL_PATH = TESTS_DIR / "eval_set.json"
ALLOWED_JURISDICTIONS = {"India", "International", "all"}
ALLOWED_INTENTS = {"definition", "purpose", "prohibition", "comparison", "explicit_provision", "general"}
ALLOWED_QUERY_TYPES = {"normal", "comparison", "explicit_provision", "abstention"}
ALLOWED_CATEGORIES = {
    "patentability", "patent_procedure", "trademarks", "geographical_indications", "designs",
    "biological_diversity", "traditional_knowledge", "ayurveda_food_regulatory",
    "international_treaties", "comparisons", "explicit_provisions", "insufficient_evidence", "out_of_scope",
}
IDENTITY_FIELDS = ("document_id", "document_name", "jurisdiction", "provision_type", "provision_number")
TARGET_FIELDS = (*IDENTITY_FIELDS, "provision_title")
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))
from app.retriever import analyze_legal_query  # noqa: E402


def _key(value: dict[str, Any], fields: tuple[str, ...] = IDENTITY_FIELDS) -> tuple[str, ...]:
    return tuple(str(value.get(field) or "") for field in fields)


def _chunk_id(chunk: dict[str, Any]) -> str:
    identity = f"{chunk.get('document_id') or ''}#chunk-{chunk.get('chunk_index')}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def validate() -> tuple[list[str], dict[str, Any]]:
    """Check schema, query uniqueness, target identity, and indexed target records."""
    errors: list[str] = []
    dataset = json.loads(HOLDOUT_PATH.read_text(encoding="utf-8-sig"))
    chunks_data = json.loads(CHUNKS_PATH.read_text(encoding="utf-8-sig"))
    original_data = json.loads(EVAL_PATH.read_text(encoding="utf-8-sig"))
    items = dataset.get("items") if isinstance(dataset, dict) else None
    chunks = chunks_data.get("chunks") if isinstance(chunks_data, dict) else None
    if not isinstance(items, list) or not isinstance(chunks, list):
        return ["Holdout and chunks files must each contain an items/chunks list."], {}
    if not 40 <= len(items) <= 50:
        errors.append(f"Expected 40-50 holdout items, found {len(items)}.")

    identities: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for chunk in chunks:
        if isinstance(chunk, dict):
            identities.setdefault(_key(chunk), []).append(chunk)
    original_queries = {
        re.sub(r"\s+", " ", str(item.get("query") or "")).strip().casefold()
        for item in original_data.get("items", []) if isinstance(item, dict)
    }
    ids: set[str] = set()
    queries: set[str] = set()
    categories: Counter[str] = Counter()
    query_types: Counter[str] = Counter()
    jurisdictions: Counter[str] = Counter()
    wanted_index_ids: set[str] = set()
    for position, item in enumerate(items, 1):
        label = f"item {position}"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be an object.")
            continue
        required = {"id", "category", "query", "jurisdiction", "intent", "query_type",
                    "expected_targets", "should_abstain", "notes"}
        if required - item.keys():
            errors.append(f"{label}: missing fields {sorted(required - item.keys())}.")
            continue
        identifier = str(item["id"])
        if identifier in ids:
            errors.append(f"{label}: duplicate id {identifier!r}.")
        ids.add(identifier)
        query = item["query"]
        if not isinstance(query, str) or not query.strip():
            errors.append(f"{label}: query must be non-empty text.")
            continue
        normalized = re.sub(r"\s+", " ", query).strip().casefold()
        if normalized in queries:
            errors.append(f"{label}: duplicate holdout query.")
        if normalized in original_queries:
            errors.append(f"{label}: duplicates an existing eval_set.json query.")
        queries.add(normalized)
        if item["jurisdiction"] not in ALLOWED_JURISDICTIONS:
            errors.append(f"{label}: invalid jurisdiction {item['jurisdiction']!r}.")
        if item["intent"] not in ALLOWED_INTENTS:
            errors.append(f"{label}: invalid intent {item['intent']!r}.")
        if item["query_type"] not in ALLOWED_QUERY_TYPES:
            errors.append(f"{label}: invalid query_type {item['query_type']!r}.")
        if item["category"] not in ALLOWED_CATEGORIES:
            errors.append(f"{label}: invalid category {item['category']!r}.")
        if not isinstance(item["should_abstain"], bool):
            errors.append(f"{label}: should_abstain must be boolean.")
        targets = item["expected_targets"]
        if not isinstance(targets, list):
            errors.append(f"{label}: expected_targets must be a list.")
            continue
        if item["should_abstain"] != (item["query_type"] == "abstention"):
            errors.append(f"{label}: abstention flag and query_type disagree.")
        if item["should_abstain"] and targets:
            errors.append(f"{label}: abstention query has expected targets.")
        if not item["should_abstain"] and not targets:
            errors.append(f"{label}: answerable query has no expected target.")
        if item["category"] == "comparisons":
            target_jurisdictions = {target.get("jurisdiction") for target in targets if isinstance(target, dict)}
            if item["jurisdiction"] != "all" or item["query_type"] != "comparison":
                errors.append(f"{label}: comparison must use query_type=comparison and jurisdiction=all.")
            if target_jurisdictions != {"India", "International"}:
                errors.append(f"{label}: comparison targets must include India and International.")
            analysis = analyze_legal_query(query)
            if analysis["intent"] != "comparison" or set(analysis["jurisdictions_requested"]) != {"India", "International"}:
                errors.append(f"{label}: query analyzer does not identify a cross-jurisdiction comparison.")
        if item["category"] == "explicit_provisions" and item["query_type"] != "explicit_provision":
            errors.append(f"{label}: explicit provision category has the wrong query type.")
        if item["query_type"] == "explicit_provision":
            analysis = analyze_legal_query(query)
            explicit = analysis["explicit_provision"]
            if not explicit or not any(
                str(target.get("provision_type") or "").rstrip("s") == explicit["type"]
                and re.sub(r"\s+", "", str(target.get("provision_number") or "")).casefold() ==
                    re.sub(r"\s+", "", explicit["number"]).casefold()
                for target in targets if isinstance(target, dict)
            ):
                errors.append(f"{label}: explicit provision reference does not match its expected target.")
        categories[str(item["category"])] += 1
        query_types[str(item["query_type"])] += 1
        jurisdictions[str(item["jurisdiction"])] += 1
        for target_index, target in enumerate(targets, 1):
            target_label = f"{label} target {target_index}"
            if not isinstance(target, dict) or set(TARGET_FIELDS) - target.keys():
                errors.append(f"{target_label}: malformed target or missing metadata.")
                continue
            matched = identities.get(_key(target), [])
            if not matched:
                errors.append(f"{target_label}: target not found in chunks.json: {_key(target)}")
                continue
            if target.get("provision_title") not in {chunk.get("provision_title") for chunk in matched}:
                errors.append(f"{target_label}: provision_title does not match source chunks.")
            if item["jurisdiction"] != "all" and target.get("jurisdiction") != item["jurisdiction"]:
                errors.append(f"{target_label}: target jurisdiction conflicts with query filter.")
            wanted_index_ids.update(_chunk_id(chunk) for chunk in matched)

    if len(items) and "India" not in {t.get("jurisdiction") for i in items for t in i.get("expected_targets", [])}:
        errors.append("Holdout targets do not cover India.")
    if len(items) and "International" not in {t.get("jurisdiction") for i in items for t in i.get("expected_targets", [])}:
        errors.append("Holdout targets do not cover International material.")

    import chromadb
    client = chromadb.PersistentClient(path=str(RAG_ROOT / "chroma_db"))
    collection = client.get_collection(name="ip_sakti_legal")
    indexed_ids = set()
    for start in range(0, len(wanted_index_ids), 500):
        response = collection.get(ids=sorted(wanted_index_ids)[start:start + 500], include=[])
        indexed_ids.update(response.get("ids", []))
    for missing in sorted(wanted_index_ids - indexed_ids):
        errors.append(f"Expected target chunk missing from Chroma: {missing}")

    summary = {
        "total": len(items), "answerable": sum(not x.get("should_abstain", False) for x in items),
        "abstentions": sum(bool(x.get("should_abstain", False)) for x in items),
        "categories": dict(categories), "query_types": dict(query_types),
        "jurisdictions": dict(jurisdictions), "unique_targets": len(wanted_index_ids),
        "chroma_records": collection.count(),
    }
    return errors, summary


def main() -> None:
    errors, summary = validate()
    if summary:
        print("Stage 6K holdout validation:")
        for key, value in summary.items():
            print(f"- {key}: {value}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Result: PASS")


if __name__ == "__main__":
    main()
