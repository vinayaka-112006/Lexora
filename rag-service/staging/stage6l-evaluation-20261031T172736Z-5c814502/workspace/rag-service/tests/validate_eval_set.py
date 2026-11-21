"""Validate the Stage 6A evaluation set against authoritative chunk metadata."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
EVAL_PATH = TESTS_DIR / "eval_set.json"
CHUNKS_PATH = RAG_ROOT / "data" / "chunks.json"
ALLOWED_JURISDICTIONS = {"India", "International", "all"}
ALLOWED_INTENTS = {"definition", "purpose", "prohibition", "comparison", "explicit_provision", "general"}
REQUIRED_ITEM_FIELDS = {"id", "category", "query", "jurisdiction", "intent", "expected_targets", "should_abstain", "notes"}
TARGET_FIELDS = ("document_id", "document_name", "jurisdiction", "provision_type", "provision_number", "provision_title")
MIN_CATEGORY_COUNTS = {
    "definitions": 2, "patentability": 2, "patent_procedure": 2, "trademarks": 2,
    "geographical_indications": 1, "designs": 1, "biological_diversity": 2,
    "traditional_knowledge": 1, "ayurveda_food_regulatory": 1, "international_treaties": 2,
    "comparisons": 3, "explicit_provisions": 3, "insufficient_evidence": 5, "out_of_scope": 1,
}


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip().casefold()


def _target_key(target: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(target.get(field) or "") for field in TARGET_FIELDS)


def validate() -> tuple[list[str], dict[str, Any]]:
    """Return validation errors and summary counts without modifying either input file."""
    errors: list[str] = []
    dataset = json.loads(EVAL_PATH.read_text(encoding="utf-8-sig"))
    chunk_data = json.loads(CHUNKS_PATH.read_text(encoding="utf-8-sig"))
    items = dataset.get("items") if isinstance(dataset, dict) else None
    chunks = chunk_data.get("chunks") if isinstance(chunk_data, dict) else None
    if not isinstance(items, list):
        return ["eval_set.json must contain an 'items' list."], {}
    if not isinstance(chunks, list):
        return ["chunks.json must contain a 'chunks' list."], {}

    valid_target_keys = {_target_key(chunk) for chunk in chunks if isinstance(chunk, dict)}
    ids: list[str] = []
    queries: list[str] = []
    categories: Counter[str] = Counter()
    jurisdiction_counts: Counter[str] = Counter()
    duplicate_targets: Counter[tuple[tuple[str, ...], ...]] = Counter()
    invalid_targets = 0
    schema_errors = 0
    abstention_count = 0
    comparison_count = 0
    explicit_count = 0
    for index, item in enumerate(items, start=1):
        label = f"item {index}"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be an object.")
            schema_errors += 1
            continue
        missing = REQUIRED_ITEM_FIELDS - item.keys()
        if missing:
            errors.append(f"{label}: missing fields {sorted(missing)}.")
            schema_errors += 1
            continue
        ids.append(str(item["id"]))
        if not isinstance(item["query"], str) or not item["query"].strip():
            errors.append(f"{label}: query must be a non-empty string.")
            schema_errors += 1
            continue
        queries.append(_normalize_query(item["query"]))
        categories[str(item["category"])] += 1
        jurisdiction_counts[str(item["jurisdiction"])] += 1
        if item["jurisdiction"] not in ALLOWED_JURISDICTIONS:
            errors.append(f"{label}: invalid jurisdiction {item['jurisdiction']!r}.")
            schema_errors += 1
        if item["intent"] not in ALLOWED_INTENTS:
            errors.append(f"{label}: invalid intent {item['intent']!r}.")
            schema_errors += 1
        if not isinstance(item["should_abstain"], bool):
            errors.append(f"{label}: should_abstain must be boolean.")
            schema_errors += 1
        targets = item["expected_targets"]
        if not isinstance(targets, list):
            errors.append(f"{label}: expected_targets must be a list.")
            schema_errors += 1
            continue
        if item["should_abstain"]:
            abstention_count += 1
            if targets:
                errors.append(f"{label}: abstention item must have no expected targets.")
                schema_errors += 1
        elif not targets:
            errors.append(f"{label}: non-abstention item needs at least one expected target.")
            schema_errors += 1
        target_keys: list[tuple[str, ...]] = []
        for target_index, target in enumerate(targets, start=1):
            if not isinstance(target, dict) or not set(TARGET_FIELDS).issubset(target):
                errors.append(f"{label} target {target_index}: missing required target metadata.")
                invalid_targets += 1
                continue
            key = _target_key(target)
            target_keys.append(key)
            if key not in valid_target_keys:
                errors.append(f"{label} target {target_index}: metadata does not exactly match chunks.json: {key!r}.")
                invalid_targets += 1
        if target_keys:
            duplicate_targets[tuple(sorted(set(target_keys)))] += 1
        if item["intent"] == "comparison" or item["category"] == "comparisons":
            comparison_count += 1
        if item["intent"] == "explicit_provision":
            explicit_count += 1

    duplicate_ids = len(ids) - len(set(ids))
    duplicate_queries = len(queries) - len(set(queries))
    if duplicate_ids:
        errors.append(f"Found {duplicate_ids} duplicate evaluation IDs.")
    if duplicate_queries:
        errors.append(f"Found {duplicate_queries} duplicate queries.")
    unjustified_duplicate_combos = sum(
        count - 1 for combination, count in duplicate_targets.items() if count > 1
    )
    if unjustified_duplicate_combos:
        errors.append(f"Found {unjustified_duplicate_combos} repeated expected-target combinations; add a target-combination-justification note only when intentional.")
    if len(items) < 30:
        errors.append("At least 30 evaluation items are required.")
    if abstention_count < 5:
        errors.append("At least 5 abstention items are required.")
    if comparison_count < 3:
        errors.append("At least 3 comparison items are required.")
    if explicit_count < 3:
        errors.append("At least 3 explicit-provision items are required.")
    for category, minimum in MIN_CATEGORY_COUNTS.items():
        if categories[category] < minimum:
            errors.append(f"Category {category!r} has {categories[category]} item(s), expected at least {minimum}.")
    target_jurisdictions = {key[2] for item in items if isinstance(item, dict)
                            for target in item.get("expected_targets", []) if isinstance(target, dict)
                            for key in [_target_key(target)]}
    if "India" not in target_jurisdictions or "International" not in target_jurisdictions:
        errors.append("Expected targets must represent both India and International material.")

    summary = {
        "total": len(items), "jurisdiction_counts": dict(jurisdiction_counts),
        "abstention_count": abstention_count, "comparison_count": comparison_count,
        "explicit_count": explicit_count, "categories": dict(categories),
        "duplicate_ids": duplicate_ids, "invalid_targets": invalid_targets,
        "duplicate_queries": duplicate_queries, "schema_errors": schema_errors,
        "duplicate_target_combinations": unjustified_duplicate_combos,
    }
    return errors, summary


def main() -> None:
    errors, summary = validate()
    if not summary:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    counts = summary["jurisdiction_counts"]
    print("Evaluation set:")
    print(f"- Total: {summary['total']}")
    print(f"- India: {counts.get('India', 0)}")
    print(f"- International: {counts.get('International', 0)}")
    print(f"- All/comparison: {counts.get('all', 0)}")
    print(f"- Abstention cases: {summary['abstention_count']}")
    print(f"- Explicit provision cases: {summary['explicit_count']}")
    print(f"- Comparison cases: {summary['comparison_count']}")
    print(f"- Categories represented: {', '.join(sorted(summary['categories']))}")
    print("Validation:")
    print(f"- Duplicate IDs: {summary['duplicate_ids']}")
    print(f"- Invalid targets: {summary['invalid_targets']}")
    print(f"- Duplicate queries: {summary['duplicate_queries']}")
    print(f"- Schema errors: {summary['schema_errors']}")
    print(f"- Duplicate target combinations: {summary['duplicate_target_combinations']}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Result: PASS")


if __name__ == "__main__":
    main()
