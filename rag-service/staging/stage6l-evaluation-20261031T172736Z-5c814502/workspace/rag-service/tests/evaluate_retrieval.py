"""Run the checked-in retrieval evaluation set and report transparent ranking metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.retriever import LegalRetriever, analyze_legal_query  # noqa: E402

EVAL_PATH = Path(__file__).with_name("eval_set.json")


def load_eval_set(path: Path = EVAL_PATH) -> list[dict[str, Any]]:
    """Load the extendable evaluation question and target definitions."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    queries = data.get("queries") if isinstance(data, dict) else None
    if not isinstance(queries, list) or not queries:
        raise ValueError("eval_set.json must contain a non-empty 'queries' list")
    return queries


def matches_target(chunk: dict[str, Any], target: dict[str, Any]) -> bool:
    """Match a result to a target using its declared document/provision/jurisdiction fields."""
    return (
        str(target.get("document_name_contains", "")).casefold()
        in str(chunk.get("document_name", "")).casefold()
        and str(target.get("provision_type", "")).casefold()
        == str(chunk.get("provision_type", "")).casefold()
        and str(target.get("provision_number", "")).casefold()
        == str(chunk.get("provision_number", "")).casefold()
        and str(target.get("jurisdiction", "")).casefold()
        == str(chunk.get("jurisdiction", "")).casefold()
    )


def evaluate() -> None:
    """Print baseline and query-aware rankings, then macro Recall@k and MRR."""
    queries = load_eval_set()
    retriever = LegalRetriever()
    top_k = 5
    recall_totals = {1: 0.0, 3: 0.0, 5: 0.0}
    reciprocal_ranks: list[float] = []
    baseline_results: list[list[dict[str, Any]]] = []
    adjusted_results: list[list[dict[str, Any]]] = []

    for item in queries:
        question = item["question"]
        targets = item["expected_targets"]
        analysis = analyze_legal_query(question)
        baseline = retriever.retrieve(question, top_k=top_k, query_aware=False)
        adjusted = retriever.retrieve(question, top_k=top_k, query_aware=True)
        baseline_results.append(baseline)
        adjusted_results.append(adjusted)
        ranks = [i for i, chunk in enumerate(adjusted, start=1)
                 if any(matches_target(chunk, target) for target in targets)]
        target_rank = min(ranks) if ranks else None
# For multiple expected targets, MRR uses the earliest matching target rank.
        reciprocal_ranks.append(1.0 / target_rank if target_rank else 0.0)
        for cutoff in recall_totals:
            found_count = sum(
                1 for target in targets
                if any(matches_target(chunk, target) for chunk in adjusted[:cutoff])
            )
            # Multiple comparison targets are valid alternatives/coverage items;
            # recall is the fraction of the declared targets found by this cutoff.
            recall_totals[cutoff] += found_count / len(targets)

        def label(chunk: dict[str, Any]) -> str:
            return (f"{chunk.get('document_name')} {chunk.get('provision_type')} "
                    f"{chunk.get('provision_number')} ({chunk.get('jurisdiction')}) "
                    f"p.{chunk.get('page_start')}-{chunk.get('page_end')}")

        print(f"\nQuestion: {question}")
        print(f"Intent: {analysis['intent']}; explicit_provision={analysis['explicit_provision']}; "
              f"jurisdictions={analysis['jurisdictions_requested']}")
        print("Expected target(s):")
        for target in targets:
            print(f"  - {target}")
        base_target = next((i for i, row in enumerate(baseline, 1)
                            if any(matches_target(row, target) for target in targets)), None)
        print(f"Baseline RRF target rank: {base_target or 'not in top 5'}")
        print("Baseline top 5:")
        for rank, chunk in enumerate(baseline, 1):
            print(f"  {rank}. {label(chunk)} | RRF={chunk['hybrid_score']:.6f}")
        print("Query-aware top 5:")
        for rank, chunk in enumerate(adjusted, 1):
            print(f"  {rank}. {label(chunk)} | final={chunk['final_score']:.6f} "
                  f"RRF={chunk['hybrid_score']:.6f} intent_bonus={chunk['intent_bonus']:.6f} "
                  f"dense={chunk.get('dense_rank')} bm25={chunk.get('bm25_rank')}")
        print(f"Target rank: {target_rank or 'not in top 5'}; found={target_rank is not None}")

    n = len(queries)
    print("\nMacro metrics (query-aware hybrid):")
    for cutoff, total in recall_totals.items():
        print(f"Recall@{cutoff}: {total / n:.4f}")
    print(f"MRR: {sum(reciprocal_ranks) / n:.4f}")


if __name__ == "__main__":
    try:
        evaluate()
    except Exception as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error




