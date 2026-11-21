"""Read-only full retrieval evaluation for the Stage 6A dataset."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
EVAL_PATH = TESTS_DIR / "eval_set.json"
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.retriever import LegalRetriever, analyze_legal_query  # noqa: E402

CUTOFFS = (1, 3, 5, 10)
CATEGORY_ORDER = (
    "definitions", "patentability", "patent_procedure", "trademarks",
    "geographical_indications", "designs", "biological_diversity",
    "traditional_knowledge", "ayurveda_food_regulatory", "international_treaties",
    "comparisons", "explicit_provisions",
)


def load_items(path: Path = EVAL_PATH) -> list[dict[str, Any]]:
    """Load Stage 6A items, leaving the legacy four-query list unused."""
    dataset = json.loads(path.read_text(encoding="utf-8-sig"))
    items = dataset.get("items") if isinstance(dataset, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("eval_set.json must contain a non-empty 'items' list")
    return items


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def matches_target(chunk: dict[str, Any], target: dict[str, Any]) -> bool:
    """Match an expected provision by stable document identity and provision metadata."""
    return (
        str(chunk.get("document_id") or "") == str(target.get("document_id") or "")
        and _normalized(chunk.get("document_name")) == _normalized(target.get("document_name"))
        and _normalized(chunk.get("jurisdiction")) == _normalized(target.get("jurisdiction"))
        and _normalized(chunk.get("provision_type")) == _normalized(target.get("provision_type"))
        and _normalized(chunk.get("provision_number")) == _normalized(target.get("provision_number"))
    )


def _target_rankings(results: list[dict[str, Any]], targets: list[dict[str, Any]]) -> list[int | None]:
    """Return each target's earliest 1-based rank in the retrieved result list."""
    ranks: list[int | None] = []
    for target in targets:
        ranks.append(next((rank for rank, row in enumerate(results, start=1)
                           if matches_target(row, target)), None))
    return ranks


def _metric_record(items: list[dict[str, Any]], rankings: dict[str, list[int | None]]) -> dict[str, Any]:
    """Compute macro Recall@k and the project's earliest-target MRR convention."""
    if not items:
        return {"queries": 0, **{f"recall@{cutoff}": 0.0 for cutoff in CUTOFFS}, "mrr": 0.0}
    recalls: dict[int, float] = {cutoff: 0.0 for cutoff in CUTOFFS}
    reciprocal_ranks: list[float] = []
    for item in items:
        target_ranks = rankings[item["id"]]
        targets = item["expected_targets"]
        for cutoff in CUTOFFS:
            found = sum(rank is not None and rank <= cutoff for rank in target_ranks)
            recalls[cutoff] += found / len(targets)
        found_ranks = [rank for rank in target_ranks if rank is not None]
        reciprocal_ranks.append(1.0 / min(found_ranks) if found_ranks else 0.0)
    count = len(items)
    return {
        "queries": count,
        **{f"recall@{cutoff}": round(total / count, 4) for cutoff, total in recalls.items()},
        "mrr": round(sum(reciprocal_ranks) / count, 4),
    }


def _label(row: dict[str, Any] | None) -> str:
    if row is None:
        return "none"
    return (f"{row.get('document_name')} {row.get('provision_type')} "
            f"{row.get('provision_number')} ({row.get('jurisdiction')})")


def evaluate() -> dict[str, Any]:
    """Run all 42 items twice, calculate read-only metrics, and print the report."""
    items = load_items()
    abstentions = [item for item in items if item["should_abstain"]]
    retrieval_items = [item for item in items if not item["should_abstain"]]
    if any(item["expected_targets"] for item in abstentions):
        raise ValueError("Abstention items must have empty expected_targets")
    if any(not item["expected_targets"] for item in retrieval_items):
        raise ValueError("Every non-abstention item must have at least one expected target")

    retriever = LegalRetriever()
    first: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        jurisdiction = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
        first[item["id"]] = retriever.retrieve(item["query"], top_k=10, jurisdiction=jurisdiction)
    second: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        jurisdiction = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
        second[item["id"]] = retriever.retrieve(item["query"], top_k=10, jurisdiction=jurisdiction)

    ranking_mismatches = sum(
        [row.get("chunk_id") for row in first[item["id"]]] !=
        [row.get("chunk_id") for row in second[item["id"]]]
        for item in items
    )
    target_ranks = {item["id"]: _target_rankings(first[item["id"]], item["expected_targets"])
                    for item in retrieval_items}
    overall = _metric_record(retrieval_items, target_ranks)
    category_metrics: dict[str, dict[str, Any]] = {}
    for category in CATEGORY_ORDER:
        selected = [item for item in retrieval_items if item["category"] == category]
        if selected:
            category_metrics[category] = _metric_record(selected, target_ranks)

    jurisdiction_violations: list[dict[str, Any]] = []
    for item in items:
        if item["jurisdiction"] not in {"India", "International"}:
            continue
        for rank, row in enumerate(first[item["id"]], start=1):
            if row.get("jurisdiction") != item["jurisdiction"]:
                jurisdiction_violations.append({
                    "id": item["id"], "rank": rank,
                    "requested": item["jurisdiction"], "returned": row.get("jurisdiction"),
                })

    explicit_rows: list[dict[str, Any]] = []
    for item in items:
        if item["intent"] != "explicit_provision" or item["should_abstain"]:
            continue
        analysis = analyze_legal_query(item["query"])
        ranks = target_ranks[item["id"]]
        expected_rank = min((rank for rank in ranks if rank is not None), default=None)
        explicit_rows.append({
            "id": item["id"], "query": item["query"],
            "requested_provision": analysis["explicit_provision"],
            "expected_provision_rank": expected_rank,
            "rank_1": expected_rank == 1,
            "top_3": expected_rank is not None and expected_rank <= 3,
            "top_5": expected_rank is not None and expected_rank <= 5,
            "top_10": expected_rank is not None and expected_rank <= 10,
        })

    comparison_rows: list[dict[str, Any]] = []
    comparison_jurisdictions: dict[int, Counter[str]] = {5: Counter(), 10: Counter()}
    for item in items:
        if item["category"] != "comparisons" or item["should_abstain"]:
            continue
        ranks = target_ranks[item["id"]]
        count5 = sum(rank is not None and rank <= 5 for rank in ranks)
        count10 = sum(rank is not None and rank <= 10 for rank in ranks)
        comparison_rows.append({
            "id": item["id"], "query": item["query"],
            "expected_target_count": len(item["expected_targets"]),
            "found_top_5": count5, "found_top_10": count10,
            "target_coverage@5": round(count5 / len(ranks), 4),
            "target_coverage@10": round(count10 / len(ranks), 4),
            "jurisdictions_top_5": dict(Counter(row.get("jurisdiction", "unknown") for row in first[item["id"]][:5])),
            "jurisdictions_top_10": dict(Counter(row.get("jurisdiction", "unknown") for row in first[item["id"]][:10])),
        })
        for cutoff in (5, 10):
            comparison_jurisdictions[cutoff].update(
                row.get("jurisdiction", "unknown") for row in first[item["id"]][:cutoff]
            )

    abstention_rows: list[dict[str, Any]] = []
    for item in abstentions:
        results = first[item["id"]]
        top = results[0] if results else None
        bm25_score = top.get("bm25_score") if top else None
        abstention_rows.append({
            "id": item["id"], "query": item["query"],
            "retrieved_results": len(results), "top_result": _label(top),
            "top_result_bm25_score": bm25_score,
            "potentially_relevant_by_existing_bm25_signal": (bm25_score > 0 if bm25_score is not None else None),
        })

    print("FULL RETRIEVAL EVALUATION")
    print("\nDataset:")
    print(f"- Total: {len(items)}")
    print(f"- Evaluated for retrieval: {len(retrieval_items)}")
    print(f"- Abstention cases: {len(abstentions)}")
    print("\nOverall (macro over non-abstention queries):")
    for metric in ("recall@1", "recall@3", "recall@5", "recall@10", "mrr"):
        print(f"- {metric.upper()}: {overall[metric]:.4f}")
    print("\nCategory metrics:")
    for category, metrics in category_metrics.items():
        print(f"- {category}: n={metrics['queries']}; " + "; ".join(
            f"{key.upper()}={metrics[key]:.4f}" for key in ("recall@1", "recall@3", "recall@5", "recall@10", "mrr")
        ))
    print("\nExplicit-provision analysis:")
    for row in explicit_rows:
        print(f"- {row['id']} requested={row['requested_provision']} rank={row['expected_provision_rank']} "
              f"rank1={row['rank_1']} top3={row['top_3']} top5={row['top_5']} top10={row['top_10']}")
    print("\nComparison analysis:")
    for row in comparison_rows:
        print(f"- {row['id']}: targets={row['expected_target_count']}; found@5={row['found_top_5']} "
              f"coverage@5={row['target_coverage@5']:.2%}; found@10={row['found_top_10']} "
              f"coverage@10={row['target_coverage@10']:.2%}; jurisdictions top5={row['jurisdictions_top_5']}; "
              f"top10={row['jurisdictions_top_10']}")
    print(f"- Aggregate comparison top-5 jurisdiction counts: {dict(comparison_jurisdictions[5])}")
    print(f"- Aggregate comparison top-10 jurisdiction counts: {dict(comparison_jurisdictions[10])}")
    print("\nAbstention retrieval observations (BM25 score > 0 is an existing lexical signal only):")
    for row in abstention_rows:
        print(f"- {row['id']}: retrieved={row['retrieved_results']}; top={row['top_result']}; "
              f"BM25={row['top_result_bm25_score']}; potentially_relevant={row['potentially_relevant_by_existing_bm25_signal']} | "
              f"{row['query']}")
    print("\nJurisdiction filter:")
    print(f"- Violations: {len(jurisdiction_violations)}")
    for violation in jurisdiction_violations:
        print(f"  {violation}")
    print("\nDeterminism:")
    print(f"- Deterministic: {'PASS' if ranking_mismatches == 0 else 'FAIL'}")
    print(f"- Ranking mismatches across {len(items)} repeated queries: {ranking_mismatches}")
    return {
        "items": items, "retrieval_items": retrieval_items, "overall": overall,
        "category_metrics": category_metrics, "explicit_rows": explicit_rows,
        "comparison_rows": comparison_rows, "abstention_rows": abstention_rows,
        "jurisdiction_violations": jurisdiction_violations,
        "deterministic": ranking_mismatches == 0, "ranking_mismatches": ranking_mismatches,
    }


if __name__ == "__main__":
    try:
        evaluate()
    except Exception as error:
        print(f"Full retrieval evaluation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
