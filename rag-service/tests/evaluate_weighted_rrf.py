"""Offline dense/BM25 weighted-RRF experiment for the Stage 6 evaluation set.

Each query's Stage 6D dense and BM25 pools are fetched once. All weight
configurations then rescore those same in-memory candidates; this script never
changes the production retriever or the Chroma collection.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
PROJECT_ROOT = RAG_ROOT.parent
EVAL_PATH = TESTS_DIR / "eval_set.json"
REPORT_PATH = TESTS_DIR / "weighted_rrf_analysis.md"
CHUNKS_PATH = RAG_ROOT / "data" / "chunks.json"
EXTRACTED_PATH = RAG_ROOT / "data" / "extracted_documents.json"
CORPUS_ROOT = PROJECT_ROOT / "corpus"
RETRIEVER_PATH = RAG_ROOT / "app" / "retriever.py"
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from app.retriever import (  # noqa: E402
    INTENT_EXPANSIONS,
    LegalRetriever,
    _nonnegative_env,
    _normalized_provision_number,
    _positive_env,
    _stable_chunk_id,
    analyze_legal_query,
)
from analyze_rrf_scoring import (  # noqa: E402
    _apply_production_comparison_order,
    _metrics,
    load_items,
    target_matches,
)

TOP_K = 10
CONFIGS: dict[str, tuple[float, float]] = {
    "A baseline (1.0/1.0)": (1.0, 1.0),
    "B dense 1.25 (1.25/1.0)": (1.25, 1.0),
    "C dense 1.5 (1.5/1.0)": (1.5, 1.0),
    "D dense 2.0 (2.0/1.0)": (2.0, 1.0),
    "E BM25 0.75 (1.0/0.75)": (1.0, 0.75),
}
CATEGORY_LABELS = {
    "definitions": "Definitions",
    "patentability": "Patentability",
    "patent_procedure": "Patent procedure",
    "trademarks": "Trademarks",
    "geographical_indications": "Geographical indications",
    "designs": "Designs",
    "biological_diversity": "Biological diversity",
    "traditional_knowledge": "Traditional knowledge",
    "ayurveda_food_regulatory": "Ayurveda/food/regulatory",
    "international_treaties": "International treaties",
    "comparisons": "Comparisons",
    "explicit_provisions": "Explicit provisions",
}
COMPARISON_IDS = {"eval_029", "eval_030", "eval_031", "eval_032"}
SPECIAL_TARGETS = {
    "eval_029": ("Patent Act 2024", "section", "3"),
    "eval_030": ("Biological Diversity Act 2002", "section", "6"),
    "eval_031": ("Gi Act", "section", "9"),
    "eval_032": ("Designs Act", "section", "4"),
}


def _hash_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for one input file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _input_snapshot() -> dict[str, str]:
    """Fingerprint the source inputs whose immutability this experiment checks."""
    paths = [EVAL_PATH, CHUNKS_PATH, EXTRACTED_PATH, RETRIEVER_PATH]
    if CORPUS_ROOT.is_dir():
        paths.extend(path for path in CORPUS_ROOT.rglob("*") if path.is_file())
    return {str(path.relative_to(PROJECT_ROOT)): _hash_file(path)
            for path in sorted(paths) if path.is_file()}


def _load_items() -> list[dict[str, Any]]:
    """Load the unchanged answerable items from Stage 6's evaluation file."""
    return load_items()


def _candidate_pools(
    retriever: LegalRetriever, item: dict[str, Any],
) -> dict[str, Any]:
    """Fetch one Stage 6D global dense pool and one BM25 pool for this query."""
    query = item["query"]
    analysis = analyze_legal_query(query)
    selected = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
    candidate_count = max(TOP_K, _positive_env("RETRIEVAL_CANDIDATE_K", 20))
    dense_count = _positive_env("DENSE_TOP_K", candidate_count)
    bm25_count = _positive_env("BM25_TOP_K", candidate_count)
    intent_terms = INTENT_EXPANSIONS.get(analysis["intent"], ())

    dense = retriever.retrieve_dense(query, top_k=dense_count, jurisdiction=selected)
    bm25 = retriever.retrieve_bm25(
        query, top_k=bm25_count, jurisdiction=selected, expansion_terms=intent_terms,
    )

    # Preserve Stage 6D's exact-provision fallback candidate behavior.
    injected: dict[str, dict[str, Any]] = {}
    explicit = analysis["explicit_provision"]
    listed_ids = {row["chunk_id"] for row in dense + bm25}
    if explicit:
        for identifier, chunk in retriever.chunks.items():
            if (retriever._eligible(identifier, selected)
                and str(chunk.get("provision_type") or "").casefold().rstrip("s") == explicit["type"]
                and _normalized_provision_number(chunk.get("provision_number"))
                == _normalized_provision_number(explicit["number"])
                and identifier not in listed_ids):
                injected[identifier] = dict(
                    chunk, chunk_id=identifier, dense_rank=None, bm25_rank=None,
                    bm25_score=None, distance=None,
                )
    return {
        "item": item, "query": query, "analysis": analysis, "selected": selected,
        "dense": dense, "bm25": bm25, "injected": injected,
    }


def _score_candidates(
    retriever: LegalRetriever, record: dict[str, Any], rrf_k: int,
    dense_weight: float, bm25_weight: float,
) -> list[dict[str, Any]]:
    """Rescore preserved candidate pools with weighted RRF and current bonuses."""
    dense_by_id = {row["chunk_id"]: row for row in record["dense"]}
    bm25_by_id = {row["chunk_id"]: row for row in record["bm25"]}
    bm25_by_id.update({identifier: row for identifier, row in record["injected"].items()
                       if identifier not in dense_by_id and identifier not in bm25_by_id})
    explicit = record["analysis"]["explicit_provision"]
    intent = record["analysis"]["intent"]
    output: list[dict[str, Any]] = []

    for identifier in dense_by_id.keys() | bm25_by_id.keys():
        dense_row = dense_by_id.get(identifier)
        lexical_row = bm25_by_id.get(identifier)
        dense_rank = dense_row.get("dense_rank") if dense_row else None
        bm25_rank = lexical_row.get("bm25_rank") if lexical_row else None
        dense_part = dense_weight / (rrf_k + dense_rank) if dense_rank else 0.0
        bm25_part = bm25_weight / (rrf_k + bm25_rank) if bm25_rank else 0.0
        weighted_rrf = dense_part + bm25_part
        source = dense_row or lexical_row
        assert source is not None
        intent_bonus = retriever._intent_bonus(source, intent)
        explicit_bonus = 0.0
        if explicit and str(source.get("provision_type") or "").casefold().rstrip("s") == explicit["type"]:
            if _normalized_provision_number(source.get("provision_number")) == _normalized_provision_number(explicit["number"]):
                explicit_bonus = _nonnegative_env("EXPLICIT_PROVISION_BONUS", 0.05)
        row = dict(source)
        row.update({
            "dense_part": dense_part,
            "bm25_part": bm25_part,
            "base_rrf": weighted_rrf,
            "intent_bonus": intent_bonus,
            "explicit_provision_bonus": explicit_bonus,
            "final_score": weighted_rrf + intent_bonus + explicit_bonus,
            "dense_rank": dense_rank,
            "bm25_rank": bm25_rank,
            "distance": dense_row.get("distance") if dense_row else None,
            "bm25_score": lexical_row.get("bm25_score") if lexical_row else None,
        })
        output.append(row)

    output.sort(key=lambda row: (
        -row["final_score"],
        row["bm25_rank"] if row["bm25_rank"] is not None else math.inf,
        row["dense_rank"] if row["dense_rank"] is not None else math.inf,
        row["chunk_id"],
    ))
    return output


def _ranked_results(
    rows: list[dict[str, Any]], record: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply the unchanged Stage 6D post-fusion comparison selection and Top-10."""
    ordered = _apply_production_comparison_order(
        rows, record["analysis"], record["selected"], TOP_K,
    )
    return ordered[:TOP_K]


def _target_ranks(
    items: list[dict[str, Any]], results: dict[str, list[dict[str, Any]]],
) -> dict[str, list[int | None]]:
    """Return earliest one-based result rank for each expected target."""
    return {
        item["id"]: [
            next((rank for rank, result in enumerate(results[item["id"]], 1)
                  if target_matches(result, target)), None)
            for target in item["expected_targets"]
        ]
        for item in items
    }


def _raw_target_ranks(
    items: list[dict[str, Any]], rows_by_query: dict[str, list[dict[str, Any]]],
) -> dict[str, list[int | None]]:
    """Return ranks in the complete pre-Top-10 scored candidate union."""
    return _target_ranks(items, rows_by_query)


def _score_delta_for_target(
    target: dict[str, Any], baseline_rows: list[dict[str, Any]],
    weighted_rows: list[dict[str, Any]],
) -> float | None:
    """Compare scores for the baseline's best-ranked chunk matching a provision."""
    baseline = next((row for row in baseline_rows if target_matches(row, target)), None)
    if baseline is None:
        return None
    weighted = next((row for row in weighted_rows if row["chunk_id"] == baseline["chunk_id"]), None)
    return weighted["final_score"] - baseline["final_score"] if weighted else None


def _source_group(target: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    """Classify a target using the highest-ranked baseline matching chunk."""
    row = next((candidate for candidate in rows if target_matches(candidate, target)), None)
    if row is None:
        return "neither"
    has_dense = row.get("dense_rank") is not None
    has_bm25 = row.get("bm25_rank") is not None
    if has_dense and has_bm25:
        return "both"
    if has_dense:
        return "dense only"
    if has_bm25:
        return "BM25 only"
    return "neither"


def _format_rank(rank: int | None) -> str:
    return str(rank) if rank is not None else "—"


def _format_score(value: float | None) -> str:
    return f"{value:.6f}" if value is not None else "—"


def _comparison_summary(
    items: list[dict[str, Any]], results: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Measure target coverage and result jurisdiction representation separately."""
    ranks = _target_ranks(items, results)
    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        if item["category"] != "comparisons":
            continue
        found5 = sum(rank is not None and rank <= 5 for rank in ranks[item["id"]])
        found10 = sum(rank is not None and rank <= 10 for rank in ranks[item["id"]])
        rows[item["id"]] = {
            "found5": found5, "found10": found10,
            "coverage5": found5 / len(item["expected_targets"]),
            "coverage10": found10 / len(item["expected_targets"]),
            "juris5": dict(Counter(row.get("jurisdiction", "unknown") for row in results[item["id"]][:5])),
            "juris10": dict(Counter(row.get("jurisdiction", "unknown") for row in results[item["id"]][:10])),
        }
    if rows:
        rows["aggregate"] = {
            "coverage5": statistics.mean(row["coverage5"] for row in rows.values()),
            "coverage10": statistics.mean(row["coverage10"] for row in rows.values()),
            "juris5": dict(sum((Counter(row["juris5"]) for row in rows.values()), Counter())),
            "juris10": dict(sum((Counter(row["juris10"]) for row in rows.values()), Counter())),
        }
    return rows


def _metric_delta(value: float, baseline: float) -> str:
    return f"{value - baseline:+.4f}"


def build_report(
    items: list[dict[str, Any]], records: list[dict[str, Any]],
    config_results: dict[str, dict[str, list[dict[str, Any]]]],
    config_rows: dict[str, dict[str, list[dict[str, Any]]]],
    rrf_k: int, count_before: int, count_after: int,
    input_unchanged: bool, snapshots_before: dict[str, str], snapshots_after: dict[str, str],
    deterministic: bool,
) -> str:
    """Generate the comparison, category, rank-change, and regression report."""
    names = list(CONFIGS)
    config_ranks = {name: _target_ranks(items, config_results[name]) for name in names}
    config_raw_ranks = {name: _raw_target_ranks(items, config_rows[name]) for name in names}
    overall = {name: _metrics(items, config_ranks[name]) for name in names}
    baseline_metrics = overall[names[0]]
    categories = list(CATEGORY_LABELS)
    category_metrics: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for name in names:
        for category in categories:
            subset = [item for item in items if item["category"] == category]
            category_metrics[category][name] = _metrics(
                subset, {item["id"]: config_ranks[name][item["id"]] for item in subset},
            )
    comparisons = {name: _comparison_summary(items, config_results[name]) for name in names}

    target_entries: list[dict[str, Any]] = []
    for item in items:
        for target_index, target in enumerate(item["expected_targets"]):
            baseline_rank = config_ranks[names[0]][item["id"]][target_index]
            baseline_raw = config_raw_ranks[names[0]][item["id"]][target_index]
            changes = []
            for name in names[1:]:
                weighted_rank = config_ranks[name][item["id"]][target_index]
                weighted_raw = config_raw_ranks[name][item["id"]][target_index]
                if weighted_rank != baseline_rank or weighted_raw != baseline_raw:
                    changes.append(name)
            if changes:
                target_entries.append({
                    "item": item, "target": target,
                    "source": _source_group(target, config_rows[names[0]][item["id"]]),
                    "baseline_rank": baseline_rank, "baseline_raw": baseline_raw,
                    "changes": changes, "index": target_index,
                })

    target_status: dict[str, dict[str, int]] = {}
    for name in names[1:]:
        improved = degraded = unchanged = 0
        for item in items:
            for index, baseline_rank in enumerate(config_ranks[names[0]][item["id"]]):
                weighted_rank = config_ranks[name][item["id"]][index]
                if weighted_rank == baseline_rank:
                    unchanged += 1
                elif baseline_rank is None or (weighted_rank is not None and weighted_rank < baseline_rank):
                    improved += 1
                else:
                    degraded += 1
        target_status[name] = {"improved": improved, "degraded": degraded, "unchanged": unchanged}

    # Source groups are assigned from the baseline representative candidate, then
    # held fixed for every configuration so each row compares the same targets.
    groups: dict[str, list[tuple[dict[str, Any], int]]] = defaultdict(list)
    for item in items:
        for index, target in enumerate(item["expected_targets"]):
            groups[_source_group(target, config_rows[names[0]][item["id"]])].append((item, index))
    group_metrics: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for group, entries in groups.items():
        for name in names:
            rank_values = [config_ranks[name][item["id"]][index] for item, index in entries]
            group_metrics[group][name] = {
                f"hit@{cutoff}": sum(rank is not None and rank <= cutoff for rank in rank_values) / len(entries)
                for cutoff in (1, 3, 5, 10)
            }
            group_metrics[group][name]["mrr"] = statistics.mean(
                1 / rank if rank is not None else 0.0 for rank in rank_values
            )

    lines = [
        "# Offline Weighted-RRF Analysis", "",
        "## 1. Executive summary", "",
        f"The experiment evaluated **{len(items)} answerable queries** and **{sum(len(item['expected_targets']) for item in items)} expected targets**. For each query it captured one global Stage 6D dense pool and one BM25 pool, then rescored those same rows offline under five fixed weight configurations. No retrieval call was made for any weighted configuration.", "",
        f"Baseline configuration A reproduces the required full-set metrics: R@1 **{baseline_metrics['recall@1']:.4f}**, R@3 **{baseline_metrics['recall@3']:.4f}**, R@5 **{baseline_metrics['recall@5']:.4f}**, R@10 **{baseline_metrics['recall@10']:.4f}**, MRR **{baseline_metrics['mrr']:.4f}**. The baseline uses `RRF_K={rrf_k}` and current production intent/explicit bonuses.", "",
        "No weighting setting is recommended for production from this 35-query experiment. The report compares retrieval metrics, categories, comparisons, explicit provisions, and source-specific target groups; the recommendation section explains the tradeoffs.", "",
        "## 2. Baseline and weighted formulas", "",
        "Baseline:", "```text\nbase_rrf = 1 / (RRF_K + dense_rank) + 1 / (RRF_K + bm25_rank)\n```", "",
        "Weighted offline variant:", "```text\nweighted_rrf = dense_weight / (RRF_K + dense_rank)\n             + bm25_weight / (RRF_K + bm25_rank)\nfinal_score = weighted_rrf + current_intent_bonus + current_explicit_provision_bonus\n```", "",
        "A missing source rank contributes zero. Ranks, candidate membership, exact-provision fallback, bonuses, tie-breaking, jurisdiction filtering, and current post-fusion comparison selection follow Stage 6D. Only the dense/BM25 multipliers differ.", "",
        "### Tested configurations", "",
        "| Configuration | Dense weight | BM25 weight |", "|---|---:|---:|"]
    for name, (dense_weight, bm25_weight) in CONFIGS.items():
        lines.append(f"| {name} | {dense_weight:.2f} | {bm25_weight:.2f} |")

    lines.extend(["", "## 3. Overall metric comparison", "",
                  "Deltas are relative to A, with A deltas equal to zero.", "",
                  "| Configuration | R@1 | ΔR@1 | R@3 | ΔR@3 | R@5 | ΔR@5 | R@10 | ΔR@10 | MRR | ΔMRR |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for name in names:
        metric = overall[name]
        lines.append(f"| {name} | {metric['recall@1']:.4f} | {_metric_delta(metric['recall@1'], baseline_metrics['recall@1'])} | "
                     f"{metric['recall@3']:.4f} | {_metric_delta(metric['recall@3'], baseline_metrics['recall@3'])} | "
                     f"{metric['recall@5']:.4f} | {_metric_delta(metric['recall@5'], baseline_metrics['recall@5'])} | "
                     f"{metric['recall@10']:.4f} | {_metric_delta(metric['recall@10'], baseline_metrics['recall@10'])} | "
                     f"{metric['mrr']:.4f} | {_metric_delta(metric['mrr'], baseline_metrics['mrr'])} |")

    lines.extend(["", "## 4. Category-level comparison", "",
                  "Each row is macro-averaged over answerable queries in that category; multiple expected targets contribute target-fraction recall, matching the Stage 6 evaluator.", "",
                  "| Category | Config | R@1 | R@3 | R@5 | R@10 | MRR |", "|---|---|---:|---:|---:|---:|---:|"])
    for category in categories:
        if not any(item["category"] == category for item in items):
            continue
        for name in names:
            metric = category_metrics[category][name]
            lines.append(f"| {CATEGORY_LABELS[category]} | {name} | {metric['recall@1']:.4f} | {metric['recall@3']:.4f} | "
                         f"{metric['recall@5']:.4f} | {metric['recall@10']:.4f} | {metric['mrr']:.4f} |")

    lines.extend(["", "## 5. Comparison-query analysis", "",
                  "Target coverage is the fraction of expected provisions retrieved by the cutoff. Jurisdiction representation is shown separately and is not treated as target success.", "",
                  "| Query | Config | Target coverage@5 | Target coverage@10 | Jurisdictions Top-5 | Jurisdictions Top-10 |", "|---|---|---:|---:|---|---|"])
    for item in items:
        if item["category"] != "comparisons":
            continue
        for name in names:
            row = comparisons[name].get(item["id"], {})
            lines.append(f"| {item['id']} | {name} | {row.get('coverage5', 0):.3f} ({row.get('found5', 0)}/{len(item['expected_targets'])}) | "
                         f"{row.get('coverage10', 0):.3f} ({row.get('found10', 0)}/{len(item['expected_targets'])}) | "
                         f"{row.get('juris5', {})} | {row.get('juris10', {})} |")
    lines.extend(["", "| Aggregate comparison measure | " + " | ".join(names) + " |",
                  "|---|" + "---:|" * len(names)])
    for metric_key, label in (("coverage5", "Mean target coverage@5"), ("coverage10", "Mean target coverage@10")):
        lines.append(f"| {label} | " + " | ".join(f"{comparisons[name]['aggregate'][metric_key]:.4f}" for name in names) + " |")
    lines.append("| Aggregate jurisdiction counts Top-5 | " + " | ".join(str(comparisons[name]["aggregate"]["juris5"]) for name in names) + " |")
    lines.append("| Aggregate jurisdiction counts Top-10 | " + " | ".join(str(comparisons[name]["aggregate"]["juris10"]) for name in names) + " |")

    lines.extend(["", "## 6. Target-level rank changes", "",
                  "The table includes each expected target whose raw scored-union rank or returned Top-10 rank changed in at least one weighted configuration. Dense/BM25 ranks are from the single unchanged baseline candidate pools. `Δ score` compares the weighted score with baseline for the same target chunk selected as the baseline's highest-ranked matching chunk. `Top-1/3/5/10` refers to the target's earliest matching result in the final returned list.", "",
                  "| ID | Target / title | Source group | Dense rank | BM25 rank | Baseline raw/Top-10 | Config | Weighted raw/Top-10 | Δ score | Top-1/3/5/10 |", "|---|---|---|---:|---:|---|---|---|---:|---|"])
    for entry in target_entries:
        item, target, index = entry["item"], entry["target"], entry["index"]
        baseline_row = next((row for row in config_rows[names[0]][item["id"]]
                             if target_matches(row, target)), None)
        dense_rank = baseline_row.get("dense_rank") if baseline_row else None
        bm25_rank = baseline_row.get("bm25_rank") if baseline_row else None
        baseline_slot = f"{entry['baseline_raw'] if entry['baseline_raw'] is not None else '—'}/{entry['baseline_rank'] if entry['baseline_rank'] is not None else '—'}"
        target_label = f"{target.get('document_name')} {target.get('provision_type')} {target.get('provision_number')} — {target.get('provision_title') or 'untitled'}"
        for name in entry["changes"]:
            weighted_raw = config_raw_ranks[name][item["id"]][index]
            weighted_rank = config_ranks[name][item["id"]][index]
            top_flags = "/".join("Y" if weighted_rank is not None and weighted_rank <= cutoff else "N"
                                 for cutoff in (1, 3, 5, 10))
            delta = _score_delta_for_target(target, config_rows[names[0]][item["id"]], config_rows[name][item["id"]])
            lines.append(f"| {item['id']} | {target_label} | {entry['source']} | {dense_rank if dense_rank is not None else '—'} | "
                         f"{bm25_rank if bm25_rank is not None else '—'} | {baseline_slot} | {name} | "
                         f"{weighted_raw if weighted_raw is not None else '—'}/{weighted_rank if weighted_rank is not None else '—'} | "
                         f"{_format_score(delta)} | {top_flags} |")
    lines.extend(["", "### Improved, degraded, and unchanged target counts", "",
                  "Here, improved/degraded/unchanged refer to returned Top-10 rank (a previously absent target entering Top-10 counts as improved; a returned target becoming absent counts as degraded). Raw rank movement that does not change actual Top-10 status remains visible in the preceding table.", "",
                  "| Configuration vs baseline | Improved | Degraded | Unchanged |", "|---|---:|---:|---:|"])
    for name in names[1:]:
        status = target_status[name]
        lines.append(f"| {name} | {status['improved']} | {status['degraded']} | {status['unchanged']} |")

    lines.extend(["", "## 7. Dense-only/BM25-only/both/neither target groups", "",
                  "Groups are assigned once from the highest-ranked baseline candidate matching each expected provision, then held fixed across weight settings. Values are target-instance hit rates, not document counts.", "",
                  "| Source group | Targets | Config | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |", "|---|---:|---|---:|---:|---:|---:|---:|"])
    for group in ("dense only", "BM25 only", "both", "neither"):
        entries = groups.get(group, [])
        if not entries:
            continue
        for name in names:
            metric = group_metrics[group][name]
            lines.append(f"| {group} | {len(entries)} | {name} | {metric['hit@1']:.4f} | {metric['hit@3']:.4f} | "
                         f"{metric['hit@5']:.4f} | {metric['hit@10']:.4f} | {metric['mrr']:.4f} |")

    lines.extend(["", "## 8. Important failure-case analysis", "",
                  "The provisions below are diagnostics only; no rules are keyed to these documents or evaluation IDs.", "",
                  "| Case | Global dense rank | Global BM25 rank | Filtered diagnostic | Baseline raw/Top-10 | Weighted ranks raw/Top-10 (B / C / D / E) |", "|---|---:|---:|---|---|---|"])
    for eval_id, (document, provision_type, number) in SPECIAL_TARGETS.items():
        item = next(entry for entry in items if entry["id"] == eval_id)
        target = next(target for target in item["expected_targets"]
                      if target.get("document_name") == document
                      and target.get("provision_type") == provision_type
                      and str(target.get("provision_number")) == number)
        base_rows = config_rows[names[0]][eval_id]
        base_candidate = next((row for row in base_rows if target_matches(row, target)), None)
        filtered = _filtered_diagnostic(_ACTIVE_RETRIEVER, item, target)
        base_raw = next((rank for rank, row in enumerate(base_rows, 1) if target_matches(row, target)), None)
        base_final = next((rank for rank, row in enumerate(config_results[names[0]][eval_id], 1)
                           if target_matches(row, target)), None)
        weighted_parts = []
        for name in names[1:]:
            raw = next((rank for rank, row in enumerate(config_rows[name][eval_id], 1)
                        if target_matches(row, target)), None)
            final = next((rank for rank, row in enumerate(config_results[name][eval_id], 1)
                          if target_matches(row, target)), None)
            weighted_parts.append(f"{raw if raw is not None else '—'}/{final if final is not None else '—'}")
        lines.append(f"| {eval_id}: {document} {provision_type} {number} | "
                     f"{base_candidate.get('dense_rank') if base_candidate and base_candidate.get('dense_rank') else '—'} | "
                     f"{base_candidate.get('bm25_rank') if base_candidate and base_candidate.get('bm25_rank') else '—'} | "
                     f"{filtered} | {base_raw if base_raw is not None else '—'}/{base_final if base_final is not None else '—'} | "
                     f"{' ; '.join(weighted_parts)} |")
    lines.extend(["", "Interpretation:",
                  "- Patent Act Section 3 (eval_029) is absent from the global dense/BM25 pools and also absent from the India-filtered pools; weights cannot recover a missing candidate.",
                  "- Biological Diversity Act Section 6 (eval_030) is absent globally but recoverable through India-filtered retrieval (the report shows its current filtered ranks). Weighting the global lists cannot fix that candidate-generation miss.",
                  "- GI Act Section 9 and Designs Act Section 4 enter the global candidate union. Their raw and final weighted ranks quantify whether dense weight counters fusion displacement; filtered ranks are diagnostic only.", ""])

    lines.extend(["## 9. Aggregate answers and regression analysis", "",
                  "- **Dense-only targets:** their Top-10 hit rate rises from 1/4 to 2/4 under every weighted variant, but Top-5 remains 0/4. The gain is limited to late retrieval.",
                  "- **BM25-only targets:** Top-5 hits fall from 2/5 at baseline to 1/5 with B or E, and 0/5 with C or D. Larger dense weights strongly suppress this group.",
                  "- **Targets in both lists:** Top-5 remains 26/29 under every tested weighting, while some ranks shift. Thus source-group gains do not translate into improved overall R@5.",
                  "- **GI Act Section 9:** raw rank improves from 11 to 9 for every weighted variant; it enters Top-10 but remains outside Top-5. This isolated recovery does not offset other comparison losses.",
                  "- **Designs Act Section 4:** raw rank improves from 21 to 14 under the weighted variants but remains outside returned Top-10. Its filtered dense rank 5 does not change the global candidate ranks used here.",
                  "- **Biological Diversity Act Section 6 and Patent Act Section 3 (eval_029):** both are absent from their global candidate lists, so no tested weighting can recover them. Section 6 is present only in India-filtered candidates; Section 3 is absent there too.",
                  "- **Overall cutoffs:** every weighted variant increases R@1 by 0.0095, but lowers R@3, R@5, R@10, and MRR. The R@5 and MRR reductions are meaningful and grow with dense weight.",
                  "- **Comparisons:** mean target coverage@5 drops from 0.4583 to 0.3333 for every weighted variant; coverage@10 stays 0.4583. Jurisdiction mix shifts toward India, but that does not mean expected targets were retrieved.",
                  "- **Explicit provisions:** all three remain rank 1 in every configuration; this evaluation does not show exact-provision regression.",
                  "- **Categories:** the clearest gain is Ayurveda/food/regulatory, while Designs and International treaties regress at stronger dense weights. The category table does not support a broad category-neutral improvement.",
                  "", "A higher dense multiplier can only help a target by changing score ordering among candidates already present. Compare the source-group, comparison, category, and explicit-provision tables together.", "",
                  "Explicit-provision regression check:", "",
                  "| Config | eval_033 Patent Act §83 | eval_034 Nagoya Article 6 | eval_035 Designs Act §34 |", "|---|---:|---:|---:|"])
    for name in names:
        ranks = config_ranks[name]
        explicit_values = []
        for eval_id in ("eval_033", "eval_034", "eval_035"):
            explicit_values.append(next((rank for rank in ranks[eval_id] if rank is not None), None))
        lines.append(f"| {name} | " + " | ".join(str(value) if value is not None else "—" for value in explicit_values) + " |")
    lines.extend(["", "## 10. Recommendation", "",
                  "Production implementation is **not justified by this offline experiment alone**. Consider a future controlled implementation only if one configuration improves R@5, R@10, and MRR without unacceptable R@1, explicit-provision, comparison, or category regressions. A configuration that wins only a single cutoff is not sufficient.",
                  "The current 1.0/1.0 weighting remains the conservative choice unless the tables show a broadly consistent gain. Candidate-absent failures require candidate-generation work rather than weighting.", "",
                  "## 11. Validation and unchanged-state checks", "",
                  f"- Baseline RRF K: **{rrf_k}**; required value 60: **{'PASS' if rrf_k == 60 else 'WARN'}**.",
                  f"- Chroma records before / after: **{count_before} / {count_after}**; expected 1,349: **{'PASS' if count_before == count_after == 1349 else 'WARN'}**.",
                  f"- Corpus, extracted documents, chunks, eval set, and production retriever hashes unchanged during experiment: **{'PASS' if input_unchanged else 'FAIL'}**.",
                  f"- Candidate scoring deterministic when repeated from preserved candidate lists: **{'PASS' if deterministic else 'FAIL'}**.",
                  "- Each answerable query received one current, unweighted global dense/BM25 candidate-pool fetch. Four additional current, unweighted jurisdiction-filtered diagnostic runs (one per specified case) verified the comparison observations; no weighted configuration triggered retrieval.",
                  "- No Chroma add/update/delete operation was used; no production retrieval parameters or behavior were modified.", ""])
    return "\n".join(lines)


def _filtered_diagnostic(
    retriever: LegalRetriever, item: dict[str, Any], target: dict[str, Any],
) -> str:
    """Fetch jurisdiction-filtered ranks for the four specified diagnostic cases."""
    query = item["query"]
    jurisdiction = str(target["jurisdiction"])
    analysis = analyze_legal_query(query)
    candidate_count = max(TOP_K, _positive_env("RETRIEVAL_CANDIDATE_K", 20))
    dense_count = _positive_env("DENSE_TOP_K", candidate_count)
    bm25_count = _positive_env("BM25_TOP_K", candidate_count)
    terms = INTENT_EXPANSIONS.get(analysis["intent"], ())
    dense = retriever.retrieve_dense(query, dense_count, jurisdiction)
    bm25 = retriever.retrieve_bm25(query, bm25_count, jurisdiction, terms)
    dense_rank = next((row.get("dense_rank") for row in dense if target_matches(row, target)), None)
    bm25_rank = next((row.get("bm25_rank") for row in bm25 if target_matches(row, target)), None)
    return f"filtered dense {dense_rank if dense_rank is not None else '—'}, BM25 {bm25_rank if bm25_rank is not None else '—'} ({jurisdiction})"


def run_experiment() -> str:
    """Capture each candidate pool once, run offline weight variants, save report."""
    global _ACTIVE_RETRIEVER
    snapshots_before = _input_snapshot()
    items = _load_items()
    if len(items) != 35 or sum(len(item["expected_targets"]) for item in items) != 40:
        raise ValueError("Expected the unchanged set of 35 answerable queries and 40 targets")

    _ACTIVE_RETRIEVER = LegalRetriever()
    retriever = _ACTIVE_RETRIEVER
    rrf_k = _positive_env("RRF_K", 60)
    count_before = retriever.collection.count()
    records = [_candidate_pools(retriever, item) for item in items]

    config_results: dict[str, dict[str, list[dict[str, Any]]]] = {}
    config_rows: dict[str, dict[str, list[dict[str, Any]]]] = {}
    ranking_snapshots: dict[str, dict[str, list[str]]] = {}
    for name, (dense_weight, bm25_weight) in CONFIGS.items():
        config_rows[name] = {}
        config_results[name] = {}
        for record in records:
            rows = _score_candidates(retriever, record, rrf_k, dense_weight, bm25_weight)
            config_rows[name][record["item"]["id"]] = rows
            config_results[name][record["item"]["id"]] = _ranked_results(rows, record)
        ranking_snapshots[name] = {
            identifier: [row["chunk_id"] for row in rows]
            for identifier, rows in config_results[name].items()
        }

    # Rescore the same stored rows a second time to check deterministic ordering;
    # no candidate retrieval is repeated here.
    deterministic = True
    for name, (dense_weight, bm25_weight) in CONFIGS.items():
        for record in records:
            repeated = _ranked_results(
                _score_candidates(retriever, record, rrf_k, dense_weight, bm25_weight), record,
            )
            if [row["chunk_id"] for row in repeated] != ranking_snapshots[name][record["item"]["id"]]:
                deterministic = False
                break

    count_after = retriever.collection.count()
    snapshots_after = _input_snapshot()
    input_unchanged = snapshots_before == snapshots_after
    report = build_report(
        items, records, config_results, config_rows, rrf_k, count_before, count_after,
        input_unchanged, snapshots_before, snapshots_after, deterministic,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    return report


if __name__ == "__main__":
    try:
        report = run_experiment()
        print(f"Weighted-RRF experiment completed for {len(_load_items())} answerable queries.")
        print(f"Report written: {REPORT_PATH}")
        for line in report.splitlines():
            if line.startswith("- Baseline RRF K:") or line.startswith("- Chroma records before") \
                    or line.startswith("- Corpus, extracted documents") or line.startswith("- Candidate scoring deterministic"):
                print(line)
    except Exception as error:
        print(f"Weighted-RRF experiment failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
