"""Analyze Stage 6D dense/BM25 candidates and hypothetical RRF rankings.

This script is diagnostic only. It calls the existing retriever methods and
does not modify retrieval code, the evaluation set, corpus data, chunks, or
the Chroma collection. It writes a Markdown report beside this file.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
EVAL_PATH = TESTS_DIR / "eval_set.json"
REPORT_PATH = TESTS_DIR / "rrf_scoring_analysis.md"
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.retriever import (  # noqa: E402
    INTENT_EXPANSIONS,
    LegalRetriever,
    _nonnegative_env,
    _normalized_provision_number,
    _positive_env,
    _stable_chunk_id,
    analyze_legal_query,
)

CUTOFFS = (1, 3, 5, 10)
SENSITIVITY_K = (10, 30, 60, 100)
COMPARISON_IDS = {"eval_029", "eval_030", "eval_031", "eval_032"}
SUBSTANTIAL_RANK_GAP = 5


def load_items() -> list[dict[str, Any]]:
    """Read the unchanged Stage 6 evaluation items."""
    payload = json.loads(EVAL_PATH.read_text(encoding="utf-8-sig"))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError("eval_set.json must contain an 'items' list")
    return [item for item in items if not item.get("should_abstain")]


def target_matches(chunk: dict[str, Any], target: dict[str, Any]) -> bool:
    """Use the same stable document and provision fields as the full evaluator."""
    normalize = lambda value: " ".join(str(value or "").split()).casefold()
    return (
        str(chunk.get("document_id") or "") == str(target.get("document_id") or "")
        and normalize(chunk.get("document_name")) == normalize(target.get("document_name"))
        and normalize(chunk.get("jurisdiction")) == normalize(target.get("jurisdiction"))
        and normalize(chunk.get("provision_type")) == normalize(target.get("provision_type"))
        and normalize(chunk.get("provision_number")) == normalize(target.get("provision_number"))
    )


def _label(row: dict[str, Any]) -> str:
    """Format a compact result identity for Markdown tables."""
    return (f"{row.get('document_name') or 'Unknown'} / {row.get('jurisdiction') or '?'} / "
            f"{row.get('provision_type') or 'general'} {row.get('provision_number') or '—'}")


def _score_candidates(
    dense: list[dict[str, Any]], lexical: list[dict[str, Any]],
    injected: dict[str, dict[str, Any]], intent: str, explicit: dict[str, Any] | None,
    rrf_k: int, include_intent_bonus: bool,
) -> list[dict[str, Any]]:
    """Apply the production reciprocal-rank formula to fixed candidate lists."""
    dense_by_id = {row["chunk_id"]: row for row in dense}
    lexical_by_id = {row["chunk_id"]: row for row in lexical}
    lexical_by_id.update({key: value for key, value in injected.items()
                          if key not in dense_by_id and key not in lexical_by_id})
    output: list[dict[str, Any]] = []
    for identifier in dense_by_id.keys() | lexical_by_id.keys():
        drow, brow = dense_by_id.get(identifier), lexical_by_id.get(identifier)
        dense_rank = drow.get("dense_rank") if drow else None
        bm25_rank = brow.get("bm25_rank") if brow else None
        dense_part = 1 / (rrf_k + dense_rank) if dense_rank else 0.0
        bm25_part = 1 / (rrf_k + bm25_rank) if bm25_rank else 0.0
        base = dense_part + bm25_part
        source = drow or brow
        assert source is not None
        row = dict(source)
        # Intent and explicit bonuses are attached by the caller because the
        # retriever instance is required for the former.
        row.update({
            "dense_part": dense_part, "bm25_part": bm25_part,
            "base_rrf": base, "dense_rank": dense_rank, "bm25_rank": bm25_rank,
            "distance": drow.get("distance") if drow else None,
            "bm25_score": brow.get("bm25_score") if brow else None,
            "intent_bonus": 0.0, "explicit_bonus": 0.0,
        })
        if include_intent_bonus:
            row["intent_bonus"] = _CURRENT_RETRIEVER._intent_bonus(source, intent)
        if explicit and str(source.get("provision_type") or "").casefold().rstrip("s") == explicit["type"]:
            if _normalized_provision_number(source.get("provision_number")) == _normalized_provision_number(explicit["number"]):
                row["explicit_bonus"] = _nonnegative_env("EXPLICIT_PROVISION_BONUS", 0.05)
        row["final_score"] = base + row["intent_bonus"] + row["explicit_bonus"]
        output.append(row)
    output.sort(key=lambda row: (
        -row["final_score"],
        row["bm25_rank"] if row["bm25_rank"] is not None else math.inf,
        row["dense_rank"] if row["dense_rank"] is not None else math.inf,
        row["chunk_id"],
    ))
    return output


def _apply_production_comparison_order(
    rows: list[dict[str, Any]], analysis: dict[str, Any], selected: str, count: int,
    query_aware: bool = True,
) -> list[dict[str, Any]]:
    """Replicate the current post-fusion comparison selection without retrieval."""
    if query_aware and analysis["intent"] == "comparison" and selected == "all":
        requested = analysis["jurisdictions_requested"]
        if "India" in requested and "International" in requested and count >= 2:
            slots = min(_positive_env("COMPARISON_JURISDICTION_SLOTS", 2), max(1, count // 2))
            threshold = _nonnegative_env("COMPARISON_DIVERSITY_MIN_SCORE", 0.014)
            reserved: list[dict[str, Any]] = []
            for jurisdiction in ("India", "International"):
                eligible = [row for row in rows if row.get("jurisdiction") == jurisdiction
                            and row["final_score"] >= threshold]
                reserved.extend(eligible[:slots])
            if len({row.get("jurisdiction") for row in reserved}) == 2:
                selected_ids = {row["chunk_id"] for row in reserved}
                for row in rows:
                    if row["chunk_id"] not in selected_ids and len(reserved) < count:
                        reserved.append(row)
                        selected_ids.add(row["chunk_id"])
                return sorted(reserved, key=lambda row: (
                    -row["final_score"],
                    row["bm25_rank"] if row["bm25_rank"] is not None else math.inf,
                    row["dense_rank"] if row["dense_rank"] is not None else math.inf,
                    row["chunk_id"],
                ))
    return rows


def _metrics(
    items: list[dict[str, Any]], rankings: dict[str, list[int | None]],
) -> dict[str, float]:
    """Compute macro target recall and earliest-target MRR."""
    count = len(items)
    metrics: dict[str, float] = {}
    for cutoff in CUTOFFS:
        total = sum(
            sum(rank is not None and rank <= cutoff for rank in rankings[item["id"]])
            / len(item["expected_targets"])
            for item in items
        )
        metrics[f"recall@{cutoff}"] = total / count if count else 0.0
    reciprocal = []
    for item in items:
        ranks = [rank for rank in rankings[item["id"]] if rank is not None]
        reciprocal.append(1 / min(ranks) if ranks else 0.0)
    metrics["mrr"] = sum(reciprocal) / count if count else 0.0
    return metrics


def _target_ranks(
    items: list[dict[str, Any]], results: dict[str, list[dict[str, Any]]],
) -> dict[str, list[int | None]]:
    """Find each expected target's one-based rank in the supplied result lists."""
    return {
        item["id"]: [
            next((rank for rank, row in enumerate(results[item["id"]], 1)
                  if target_matches(row, target)), None)
            for target in item["expected_targets"]
        ]
        for item in items
    }


def _target_scoring_row(
    target: dict[str, Any], rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    return next((row for row in rows if target_matches(row, target)), None)


def _prepare_query(item: dict[str, Any]) -> dict[str, Any]:
    """Generate the exact global candidates and scoring inputs used by Stage 6D."""
    query = item["query"]
    analysis = analyze_legal_query(query)
    selected = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
    final_count = 10
    candidate_count = max(final_count, _positive_env("RETRIEVAL_CANDIDATE_K", 20))
    dense_count = _positive_env("DENSE_TOP_K", candidate_count)
    bm25_count = _positive_env("BM25_TOP_K", candidate_count)
    expansions = INTENT_EXPANSIONS.get(analysis["intent"], ())
    dense = _CURRENT_RETRIEVER.retrieve_dense(query, top_k=dense_count, jurisdiction=selected)
    lexical = _CURRENT_RETRIEVER.retrieve_bm25(
        query, top_k=bm25_count, jurisdiction=selected, expansion_terms=expansions,
    )
    injected: dict[str, dict[str, Any]] = {}
    explicit = analysis["explicit_provision"]
    if explicit:
        for identifier, chunk in _CURRENT_RETRIEVER.chunks.items():
            if (_CURRENT_RETRIEVER._eligible(identifier, selected)
                and str(chunk.get("provision_type") or "").casefold().rstrip("s") == explicit["type"]
                and _normalized_provision_number(chunk.get("provision_number"))
                == _normalized_provision_number(explicit["number"])
                and identifier not in {row["chunk_id"] for row in dense + lexical}):
                injected[identifier] = dict(
                    chunk, chunk_id=identifier, dense_rank=None, bm25_rank=None,
                    bm25_score=None, distance=None,
                )
    rows = _score_candidates(dense, lexical, injected, analysis["intent"], explicit, 60, True)
    ordered = _apply_production_comparison_order(rows, analysis, selected, final_count)
    actual = _CURRENT_RETRIEVER.retrieve(query, top_k=final_count, jurisdiction=selected)
    exact_match = [row["chunk_id"] for row in ordered[:final_count]] == [row["chunk_id"] for row in actual]
    rank_by_id = {row["chunk_id"]: rank for rank, row in enumerate(actual, 1)}
    raw_rank_by_id = {row["chunk_id"]: rank for rank, row in enumerate(rows, 1)}
    return {
        "item": item, "analysis": analysis, "selected": selected,
        "dense": dense, "lexical": lexical, "injected": injected,
        "scored": rows, "ordered": ordered, "actual": actual,
        "reproduction_matches": exact_match, "rank_by_id": rank_by_id,
        "raw_rank_by_id": raw_rank_by_id,
        "scored_by_id": {row["chunk_id"]: row for row in rows},
    }


def _fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _cell(value: Any) -> str:
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")


def _rank_source(record: dict[str, Any], target_row: dict[str, Any] | None) -> str:
    if target_row is None:
        return "neither (not explicitly injected)"
    dense = target_row["dense_rank"] is not None
    lexical = target_row["bm25_rank"] is not None
    if dense and lexical:
        return "both"
    if dense:
        return "dense only"
    if lexical:
        return "BM25 only"
    return "neither (explicitly injected)"


def build_report(records: list[dict[str, Any]]) -> str:
    """Build the complete human-readable analysis from fixed candidate lists."""
    items = [record["item"] for record in records]
    by_id = {record["item"]["id"]: record for record in records}
    target_records: list[dict[str, Any]] = []
    for record in records:
        item = record["item"]
        for target in item["expected_targets"]:
            scored = _target_scoring_row(target, record["scored"])
            candidate_status = _rank_source(record, scored)
            hybrid_rank = record["rank_by_id"].get(scored["chunk_id"]) if scored else None
            target_records.append({
                "item": item, "target": target, "scored": scored,
                "status": candidate_status, "hybrid_rank": hybrid_rank,
                "raw_rank": record["raw_rank_by_id"].get(scored["chunk_id"]) if scored else None,
                "dense_rank": scored.get("dense_rank") if scored else None,
                "bm25_rank": scored.get("bm25_rank") if scored else None,
            })

    all_target_count = len(target_records)
    source_counts = Counter(row["status"].split(" (")[0] for row in target_records)
    missed = [row for row in target_records if row["hybrid_rank"] is None or row["hybrid_rank"] > 5]
    rank_mismatches = [r["item"]["id"] for r in records if not r["reproduction_matches"]]
    current_results = {r["item"]["id"]: r["actual"] for r in records}
    current_ranks = _target_ranks(items, current_results)
    baseline_metrics = _metrics(items, current_ranks)

    # Sensitivity rankings reuse every already generated candidate list and alter
    # only the RRF K value in the score calculation.
    k_metrics: dict[int, dict[str, float]] = {}
    k_comparisons: dict[int, tuple[float, float]] = {}
    for value in SENSITIVITY_K:
        ranked: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            data = _score_candidates(
                record["dense"], record["lexical"], record["injected"],
                record["analysis"]["intent"], record["analysis"]["explicit_provision"],
                value, True,
            )
            data = _apply_production_comparison_order(
                data, record["analysis"], record["selected"], 10,
            )
            ranked[record["item"]["id"]] = data[:10]
        ranked_targets = _target_ranks(items, ranked)
        k_metrics[value] = _metrics(items, ranked_targets)
        compare_items = [item for item in items if item["id"] in COMPARISON_IDS]
        compare_scores = []
        for cutoff in (5, 10):
            hit = sum(
                sum(rank is not None and rank <= cutoff for rank in ranked_targets[item["id"]])
                / len(item["expected_targets"])
                for item in compare_items
            )
            compare_scores.append(hit / len(compare_items) if compare_items else 0.0)
        k_comparisons[value] = (compare_scores[0], compare_scores[1])

    no_bonus_results: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        ranked = _score_candidates(
            record["dense"], record["lexical"], record["injected"],
            record["analysis"]["intent"], record["analysis"]["explicit_provision"],
            60, False,
        )
        no_bonus_results[record["item"]["id"]] = _apply_production_comparison_order(
            ranked, record["analysis"], record["selected"], 10,
        )[:10]
    no_bonus_ranks = _target_ranks(items, no_bonus_results)
    no_bonus_metrics = _metrics(items, no_bonus_ranks)
    target_rank_changes = 0
    target_rank_improved = 0
    target_rank_worsened = 0
    bonus_delta_values: list[float] = []
    for target_row in target_records:
        item_id = target_row["item"]["id"]
        index = target_row["item"]["expected_targets"].index(target_row["target"])
        prod_rank = current_ranks[item_id][index]
        no_bonus_rank = no_bonus_ranks[item_id][index]
        if prod_rank != no_bonus_rank:
            target_rank_changes += 1
            if no_bonus_rank is None or (prod_rank is not None and prod_rank < no_bonus_rank):
                target_rank_improved += 1
            else:
                target_rank_worsened += 1
        if target_row["scored"]:
            bonus_delta_values.append(target_row["scored"]["intent_bonus"])

    # Descriptive cross-signal competition counts for failed targets.
    dense_target_with_bm_competitor = 0
    bm_target_with_dense_competitor = 0
    both_outside5 = 0
    one_outside5 = 0
    dense_gap_cases = 0
    bm_gap_cases = 0
    dense_ranks_missed = []
    bm_ranks_missed = []
    hybrid_ranks_missed = []
    raw_rrf_ranks_missed = []
    source_rrf_scores: dict[str, list[float]] = {"both": [], "dense only": [], "BM25 only": []}
    source_top10: Counter[str] = Counter()
    source_top5: Counter[str] = Counter()
    all_candidate_source_counts: Counter[str] = Counter()
    all_candidate_top10_counts: Counter[str] = Counter()
    all_candidate_dense_ranks: dict[str, list[int]] = {"both": [], "dense only": [], "BM25 only": [], "neither": []}
    all_candidate_bm25_ranks: dict[str, list[int]] = {"both": [], "dense only": [], "BM25 only": [], "neither": []}
    for record in records:
        for candidate in record["scored"]:
            group = ("both" if candidate.get("dense_rank") is not None and candidate.get("bm25_rank") is not None
                     else "dense only" if candidate.get("dense_rank") is not None
                     else "BM25 only" if candidate.get("bm25_rank") is not None else "neither")
            all_candidate_source_counts[group] += 1
            if group in all_candidate_dense_ranks:
                if candidate.get("dense_rank") is not None:
                    all_candidate_dense_ranks[group].append(candidate["dense_rank"])
                if candidate.get("bm25_rank") is not None:
                    all_candidate_bm25_ranks[group].append(candidate["bm25_rank"])
        for result in record["actual"]:
            candidate = record["scored_by_id"].get(result["chunk_id"], {})
            group = ("both" if candidate.get("dense_rank") is not None and candidate.get("bm25_rank") is not None
                     else "dense only" if candidate.get("dense_rank") is not None
                     else "BM25 only" if candidate.get("bm25_rank") is not None else "neither")
            all_candidate_top10_counts[group] += 1
    for row in target_records:
        scored = row["scored"]
        if scored:
            group = row["status"].split(" (")[0]
            if group in source_rrf_scores:
                source_rrf_scores[group].append(scored["base_rrf"])
            if row["hybrid_rank"] is not None and row["hybrid_rank"] <= 10:
                source_top10[group] += 1
            if row["hybrid_rank"] is not None and row["hybrid_rank"] <= 5:
                source_top5[group] += 1
        if row not in missed:
            continue
        dr, br, hr = row["dense_rank"], row["bm25_rank"], row["hybrid_rank"]
        if dr is not None:
            dense_ranks_missed.append(dr)
        if br is not None:
            bm_ranks_missed.append(br)
        if hr is not None:
            hybrid_ranks_missed.append(hr)
        if row["raw_rank"] is not None:
            raw_rrf_ranks_missed.append(row["raw_rank"])
        if dr is not None and br is not None:
            both_outside5 += 1
        elif dr is not None or br is not None:
            one_outside5 += 1
        raw_hr = by_id[row["item"]["id"]]["raw_rank_by_id"].get(scored["chunk_id"]) if scored else None
        if dr is not None and scored and raw_hr is not None:
            competitors = [r for r in by_id[row["item"]["id"]]["scored"]
                           if by_id[row["item"]["id"]]["raw_rank_by_id"].get(r["chunk_id"], 999) < raw_hr]
            if any(r.get("bm25_rank") is not None for r in competitors):
                dense_target_with_bm_competitor += 1
        if br is not None and scored and raw_hr is not None:
            competitors = [r for r in by_id[row["item"]["id"]]["scored"]
                           if by_id[row["item"]["id"]]["raw_rank_by_id"].get(r["chunk_id"], 999) < raw_hr]
            if any(r.get("dense_rank") is not None for r in competitors):
                bm_target_with_dense_competitor += 1
        if row["raw_rank"] is not None and dr is not None and row["raw_rank"] >= dr + SUBSTANTIAL_RANK_GAP:
            dense_gap_cases += 1
        if row["raw_rank"] is not None and br is not None and row["raw_rank"] >= br + SUBSTANTIAL_RANK_GAP:
            bm_gap_cases += 1

    lines: list[str] = [
        "# Stage 6F RRF Scoring Analysis", "",
        "## 1. Executive summary", "",
        f"Analyzed **{len(items)} answerable queries** and **{all_target_count} expected target instances**. "
        f"The analysis reproduced production Top-10 rankings for {len(records) - len(rank_mismatches)}/{len(records)} queries "
        "using the fixed candidate lists and Stage 6D score formula.", "",
        f"The current full-evaluation baseline from the checked-in evaluator is R@1 **{baseline_metrics['recall@1']:.4f}**, "
        f"R@3 **{baseline_metrics['recall@3']:.4f}**, R@5 **{baseline_metrics['recall@5']:.4f}**, "
        f"R@10 **{baseline_metrics['recall@10']:.4f}**, MRR **{baseline_metrics['mrr']:.4f}**. "
        f"Candidate-list score reproduction mismatches: **{len(rank_mismatches)}**.", "",
        "The evidence separates two broad problems: targets missing from candidate generation cannot be fixed by RRF; "
        "targets present in one or both lists can be outranked by candidates with more combined rank contributions. "
        "All competitor observations below are descriptive and do not establish semantic relevance or legal correctness.", "",
        "## 2. Current RRF formula and explanation", "",
        "For dense rank `d`, BM25 rank `b`, and current `RRF_K=60`, Stage 6D computes:", "",
        "```text\nbase_rrf = (1 / (60 + d), if dense candidate else 0)\n         + (1 / (60 + b), if BM25 candidate else 0)\nfinal_score = base_rrf + intent_bonus + explicit_provision_bonus\n```", "",
        "Results sort by descending final score, then BM25 rank, dense rank, and stable chunk ID. Candidate pools default to 20. "
        "Intent bonuses are small fixed/configurable additions; an exact explicit-provision match can receive the configured explicit bonus.", "",
        "## 3. Aggregate target-source statistics", "",
        f"- Target instances: **{all_target_count}**.",
        f"- Dense only: **{source_counts['dense only']}**; BM25 only: **{source_counts['BM25 only']}**; both: **{source_counts['both']}**; neither: **{source_counts['neither']}**.",
        f"- Failure targets (hybrid rank >5 or absent from returned Top-10): **{len(missed)}**.",
        f"- Among failure targets: both candidate lists **{both_outside5}**; exactly one list **{one_outside5}**; neither list **{source_counts['neither']}** (the latter includes all absent targets, including any not in the failure subset).",
        f"- Failed dense-only targets with at least one higher-ranked BM25-supported competitor: **{dense_target_with_bm_competitor}**.",
        f"- Failed BM25-only targets with at least one higher-ranked dense-supported competitor: **{bm_target_with_dense_competitor}**.",
        f"- Substantially worse than dense: **{dense_gap_cases}**; substantially worse than BM25: **{bm_gap_cases}**. Definition: raw RRF rank is at least {SUBSTANTIAL_RANK_GAP} positions below that source rank; targets absent from the scored candidate union are excluded.",
        f"- Mean/median dense rank among failed targets where present: **{statistics.mean(dense_ranks_missed):.2f}/{statistics.median(dense_ranks_missed):.1f}**." if dense_ranks_missed else "- Failed targets have no dense ranks.",
        f"- Mean/median BM25 rank among failed targets where present: **{statistics.mean(bm_ranks_missed):.2f}/{statistics.median(bm_ranks_missed):.1f}**." if bm_ranks_missed else "- Failed targets have no BM25 ranks.",
        f"- Mean/median hybrid rank among failed targets returned in Top-10: **{statistics.mean(hybrid_ranks_missed):.2f}/{statistics.median(hybrid_ranks_missed):.1f}**." if hybrid_ranks_missed else "- No failed target was returned in Top-10.", "",
        f"- Mean/median raw RRF rank among failed targets present in the scored union: **{statistics.mean(raw_rrf_ranks_missed):.2f}/{statistics.median(raw_rrf_ranks_missed):.1f}**." if raw_rrf_ranks_missed else "- No failed target was present in the scored union.",
        "### Candidate-source group comparison", "",
        "Counts below are expected target instances, not all retrieved chunks. An RRF score distribution cannot alone measure legal relevance.", "",
        "| Target source group | Targets | Mean base RRF | In hybrid Top-5 | In hybrid Top-10 |", "|---|---:|---:|---:|---:|",
    ]
    for group in ("both", "dense only", "BM25 only"):
        values = source_rrf_scores[group]
        lines.append(f"| {group} | {source_counts[group]} | {statistics.mean(values):.6f} | {source_top5[group]} | {source_top10[group]} |" if values
                     else f"| {group} | {source_counts[group]} | — | {source_top5[group]} | {source_top10[group]} |")
    lines.extend(["", "Across all retrieved candidates (not only expected targets), source group frequencies are:", "",
                  "| Candidate source group | Candidate rows across queries | Rows in actual Top-10 | Mean dense rank | Mean BM25 rank |", "|---|---:|---:|---:|---:|"])
    for group in ("both", "dense only", "BM25 only", "neither"):
        dvals, bvals = all_candidate_dense_ranks[group], all_candidate_bm25_ranks[group]
        lines.append(f"| {group} | {all_candidate_source_counts[group]} | {all_candidate_top10_counts[group]} | "
                     f"{statistics.mean(dvals):.2f}" if dvals else
                     f"| {group} | {all_candidate_source_counts[group]} | {all_candidate_top10_counts[group]} | —")
        if dvals:
            lines[-1] += f" | {statistics.mean(bvals):.2f} |" if bvals else " | — |"
        else:
            lines[-1] += f" | {statistics.mean(bvals):.2f} |" if bvals else " | — |"
    total_candidate_rows = sum(all_candidate_source_counts.values())
    total_top10_rows = sum(all_candidate_top10_counts.values())
    if total_candidate_rows and total_top10_rows:
        both_candidate_share = all_candidate_source_counts["both"] / total_candidate_rows
        both_top10_share = all_candidate_top10_counts["both"] / total_top10_rows
        lines.extend(["", f"Two-source candidates make up **{both_candidate_share:.1%}** of the candidate rows and **{both_top10_share:.1%}** of actual Top-10 slots across these queries. This is consistent with RRF's additive two-signal advantage, but it is not evidence that those results are less relevant or that mediocre individual ranks should be disregarded."])

    lines.extend(["", "## 4. Target-level failure table", "",
        "This table includes every expected target outside hybrid Top-5 or absent from Top-10. `Not returned (raw RRF #N)` means a candidate received a score but did not appear in the final Top-10; `absent` means neither global candidate list contained it (unless explicitly injected).", "",
                  "| ID | Category | Query | Intent | Expected target | Dense r / distance | BM25 r / score | Dense RRF | BM25 RRF | Base RRF | Intent + explicit | Final score | Raw RRF rank / actual Top-10 rank | Candidate source |", "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"])
    for row in missed:
        item, target, scored = row["item"], row["target"], row["scored"]
        expected = (f"{target.get('document_name')} / {target.get('jurisdiction')} / "
                    f"{target.get('provision_type')} {target.get('provision_number')} — {target.get('provision_title') or 'untitled'}")
        lines.append("| " + " | ".join(_cell(value) for value in (
            item["id"], item["category"], item["query"], analyze_legal_query(item["query"])["intent"], expected,
            f"{scored.get('dense_rank')} / {_fmt(scored.get('distance'))}" if scored else "—",
            f"{scored.get('bm25_rank')} / {_fmt(scored.get('bm25_score'))}" if scored else "—",
            _fmt(scored.get("dense_part")) if scored else "—",
            _fmt(scored.get("bm25_part")) if scored else "—",
            _fmt(scored.get("base_rrf")) if scored else "—",
            f"{_fmt(scored.get('intent_bonus'))} + {_fmt(scored.get('explicit_bonus'))}" if scored else "—",
            _fmt(scored.get("final_score")) if scored else "—",
            f"{row['raw_rank']} / {row['hybrid_rank'] if row['hybrid_rank'] is not None else 'not returned'}"
            if row["scored"] else "absent / not returned",
            row["status"],
        )) + " |")

    lines.extend(["", "### Higher-ranked competitors for present targets", "",
                  "Up to five results that ranked above each failed target are shown. Contributions are calculated at K=60; a single-source competitor has a zero contribution from the other source.", ""])
    for row in missed:
        scored = row["scored"]
        if not scored:
            continue
        record = by_id[row["item"]["id"]]
        target_rank = record["rank_by_id"].get(scored["chunk_id"])
        raw_rank = record["raw_rank_by_id"].get(scored["chunk_id"])
        if target_rank is not None:
            competitors = record["actual"][:target_rank - 1]
        elif raw_rank is not None:
            competitors = record["scored"][:raw_rank - 1]
        else:
            continue
        competitors = competitors[:5]
        rank_label = target_rank if target_rank is not None else f"not returned (raw RRF #{raw_rank})"
        lines.extend([f"#### {row['item']['id']} — {_label(scored)} (actual hybrid rank: {rank_label}; raw RRF rank: {raw_rank})", "",
                      "| Rank | Document / jurisdiction / provision | Dense rank | BM25 rank | Dense RRF | BM25 RRF | Final score |", "|---:|---|---:|---:|---:|---:|---:|"])
        for competitor in competitors:
            lines.append(f"| {record['rank_by_id'].get(competitor['chunk_id'])} | {_cell(_label(competitor))} | "
                         f"{_cell(competitor.get('dense_rank'))} | {_cell(competitor.get('bm25_rank'))} | "
                         f"{_fmt(competitor.get('dense_part'))} | {_fmt(competitor.get('bm25_part'))} | {_fmt(competitor.get('final_score'))} |")
        if len(competitors) == 0:
            lines.append("No higher-ranked candidate.")
        lines.append("")

    lines.extend(["## 5. Detailed comparison-query analysis", "",
                  "The four Stage 6C/6D comparison items are reconstructed from the current global candidate pools. Filtered ranks are a separate diagnostic run within the target's own jurisdiction and do not affect global scores.", ""])
    for identifier in sorted(COMPARISON_IDS):
        record = by_id.get(identifier)
        if not record:
            lines.append(f"- {identifier}: not present in the answerable evaluation items.")
            continue
        item = record["item"]
        lines.extend([f"### {identifier}", "", f"Query: {item['query']}",
                      f"Intent: `{record['analysis']['intent']}`; requested jurisdictions: `{record['analysis']['jurisdictions_requested'] or ['all']}`.", "",
                      "| Expected target | Global dense rank / distance | Global BM25 rank / score | Dense RRF | BM25 RRF | Base RRF | Intent bonus | Explicit bonus | Final score | Raw RRF rank / actual Top-10 rank |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"])
        for target in item["expected_targets"]:
            scored = _target_scoring_row(target, record["scored"])
            rank = record["rank_by_id"].get(scored["chunk_id"]) if scored else None
            lines.append("| " + " | ".join(_cell(v) for v in (
                f"{target.get('document_name')} {target.get('provision_type')} {target.get('provision_number')} — {target.get('provision_title') or 'untitled'}",
                f"{scored.get('dense_rank')} / {_fmt(scored.get('distance'))}" if scored else "absent",
                f"{scored.get('bm25_rank')} / {_fmt(scored.get('bm25_score'))}" if scored else "absent",
                _fmt(scored.get("dense_part")) if scored else "—",
                _fmt(scored.get("bm25_part")) if scored else "—",
                _fmt(scored.get("base_rrf")) if scored else "—",
                _fmt(scored.get("intent_bonus")) if scored else "—",
                _fmt(scored.get("explicit_bonus")) if scored else "—",
                _fmt(scored.get("final_score")) if scored else "—",
                (f"{record['raw_rank_by_id'].get(scored['chunk_id'])} / {rank if rank is not None else 'not returned'}"
                 if scored else "absent / not returned"),
            )) + " |")
        # Show independently filtered availability for each target's jurisdiction.
        lines.extend(["", "Filtered-candidate check:"])
        dense_count = _positive_env("DENSE_TOP_K", max(10, _positive_env("RETRIEVAL_CANDIDATE_K", 20)))
        bm25_count = _positive_env("BM25_TOP_K", max(10, _positive_env("RETRIEVAL_CANDIDATE_K", 20)))
        expansions = INTENT_EXPANSIONS.get(record["analysis"]["intent"], ())
        for target in item["expected_targets"]:
            jurisdiction = target.get("jurisdiction")
            drows = _CURRENT_RETRIEVER.retrieve_dense(item["query"], dense_count, jurisdiction)
            brows = _CURRENT_RETRIEVER.retrieve_bm25(item["query"], bm25_count, jurisdiction, expansions)
            dr = next((r.get("dense_rank") for r in drows if target_matches(r, target)), None)
            br = next((r.get("bm25_rank") for r in brows if target_matches(r, target)), None)
            lines.append(f"- {target.get('document_name')} {target.get('provision_type')} {target.get('provision_number')} ({jurisdiction}): filtered dense rank `{dr}`, BM25 rank `{br}`.")
        lines.append("")

    lines.extend(["## 6. Dense vs BM25 vs hybrid", "",
                  f"- Dense-supported failed targets with BM25-supported higher competitors: **{dense_target_with_bm_competitor}**. This describes co-occurrence, not causal proof.",
                  f"- BM25-supported failed targets with dense-supported higher competitors: **{bm_target_with_dense_competitor}**.",
                  f"- Targets in both candidate lists but outside Top-5: **{both_outside5}**; targets in exactly one list but outside Top-5: **{one_outside5}**; targets absent from both candidate lists: **{source_counts['neither']}**.",
                  f"- Substantial rank displacement threshold: hybrid rank ≥ source rank + {SUBSTANTIAL_RANK_GAP}. Dense comparisons: **{dense_gap_cases}**; BM25 comparisons: **{bm_gap_cases}**.",
                  "- Two-list candidates receive two positive RRF terms, so they can outscore single-list candidates even when each individual rank is less favorable. The group table above measures the pattern among expected targets; it does not show that every two-list result is more relevant.",
                  "- BM25 may return exact names, section headings, and legal terms that dense search ranks lower; the competitor tables show concrete instances through source ranks and raw scores, without attributing correctness.", ""])

    lines.extend(["## 7. RRF-K sensitivity analysis", "",
                  "Each K uses the same per-query dense/BM25 candidate lists, then recomputes RRF and preserves current intent/explicit bonuses and current post-fusion behavior. Production remains K=60.", "",
                  "| Hypothetical K | R@1 | R@3 | R@5 | R@10 | MRR | Comparison coverage@5 | Comparison coverage@10 |", "|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for value in SENSITIVITY_K:
        metrics = k_metrics[value]
        cov5, cov10 = k_comparisons[value]
        lines.append(f"| {value} | {metrics['recall@1']:.4f} | {metrics['recall@3']:.4f} | {metrics['recall@5']:.4f} | {metrics['recall@10']:.4f} | {metrics['mrr']:.4f} | {cov5:.4f} | {cov10:.4f} |")
    lines.extend(["", f"Compared with K=60, K=10 raises R@3 by {k_metrics[10]['recall@3'] - k_metrics[60]['recall@3']:+.4f} and R@10 by {k_metrics[10]['recall@10'] - k_metrics[60]['recall@10']:+.4f}, but lowers R@1 by {k_metrics[10]['recall@1'] - k_metrics[60]['recall@1']:+.4f} and MRR by {k_metrics[10]['mrr'] - k_metrics[60]['mrr']:+.4f}; comparison coverage does not change. Thus K materially changes some rank cutoffs on this set, but offers no comparison-query recovery and has a real tradeoff.",
                  "K changes affect only candidates already present in the fixed union. No K value can recover an expected target missing from both candidate lists. Treat these differences as exploratory until reproduced on independent queries.", ""])

    lines.extend(["## 8. Intent-bonus sensitivity analysis", "",
                  "The offline ablation sets only the current intent bonus to zero; candidate generation, K=60, and explicit-provision bonus remain unchanged.", "",
                  "| Ranking mode | R@1 | R@3 | R@5 | R@10 | MRR |", "|---|---:|---:|---:|---:|---:|"])
    lines.append(f"| Production bonuses | {baseline_metrics['recall@1']:.4f} | {baseline_metrics['recall@3']:.4f} | {baseline_metrics['recall@5']:.4f} | {baseline_metrics['recall@10']:.4f} | {baseline_metrics['mrr']:.4f} |")
    lines.append(f"| Intent bonus zeroed | {no_bonus_metrics['recall@1']:.4f} | {no_bonus_metrics['recall@3']:.4f} | {no_bonus_metrics['recall@5']:.4f} | {no_bonus_metrics['recall@10']:.4f} | {no_bonus_metrics['mrr']:.4f} |")
    lines.extend(["", f"Expected-target ranks changed for **{target_rank_changes}/{all_target_count}** targets: **{target_rank_improved}** ranked better with the production bonus and **{target_rank_worsened}** ranked worse (ties/unavailable ranks excluded from those counts). The observed bonus values span {_fmt(min(bonus_delta_values), 4) if bonus_delta_values else '—'} to {_fmt(max(bonus_delta_values), 4) if bonus_delta_values else '—'}. The full metric difference is R@1 {no_bonus_metrics['recall@1'] - baseline_metrics['recall@1']:+.4f}, R@3 {no_bonus_metrics['recall@3'] - baseline_metrics['recall@3']:+.4f}, R@5 {no_bonus_metrics['recall@5'] - baseline_metrics['recall@5']:+.4f}, R@10 {no_bonus_metrics['recall@10'] - baseline_metrics['recall@10']:+.4f}, and MRR {no_bonus_metrics['mrr'] - baseline_metrics['mrr']:+.4f} with the intent bonus zeroed. In this set the bonus materially changes target ordering and aggregate metrics, although it cannot add a target absent from both candidate lists.", ""])

    lines.extend(["## 9. Root-cause assessment", "",
                  "- **Candidate generation:** the decisive limitation for targets absent from both global pools. RRF cannot recover them. The four comparison diagnostics test whether jurisdiction-filtered pools contain those provisions.",
                  "- **RRF fusion:** relevant where targets appear in a source list but rank beyond the returned cutoff. The one-source vs two-source contribution pattern explains how a result can be outranked; the competitor tables quantify those cases.",
                  "- **Intent bonus:** the zero-bonus ablation changes aggregate metrics and several target ranks, so it is a material part of current ordering for this set. It can address near-tie ranking but cannot fix candidate absence; any tuning needs broader validation.",
                  "- **Overall:** likely a combination of candidate-generation misses and fusion competition, not a single global cause. The report distinguishes these observable cases and avoids assigning semantic causation.",
                  "- **RRF_K=60:** lower K raises R@3/R@10 but lowers R@1/MRR here, without changing comparison coverage. That tradeoff makes K a possible general sensitivity parameter, not a proven improvement; it needs independent validation.", ""])

    lines.extend(["## 10. Generalizable recommendations for a possible future change", "",
                  "1. Separate candidate absence from fusion displacement in subsequent experiments; only test candidate generation when the target is missing from the global union.",
                  "2. If testing fusion, compare a small set of principled rank-fusion alternatives on fixed candidate pools, with full-query metrics and per-category safeguards.",
                  "3. Retain deterministic tie-breaking and evaluate source-specific rank changes, not only aggregate recall.",
                  "4. Assess effects on explicit provisions, comparison evidence, jurisdiction filters, and non-answerable queries before accepting a change.",
                  "5. Validate any promising result on a separate, unchanged holdout or newly authored evaluation set before changing production.", "",
                  "### Approaches that would overfit and should not be used", "",
                  "- boosts keyed to evaluation IDs, query text, treaty/document names, specific sections/articles, or individual expected targets;",
                  "- a blanket India preference or a manual score boost for one jurisdiction;",
                  "- choosing a new K solely because it improves these 35 answerable queries;",
                  "- changing the evaluation labels or set to make a proposed ranker pass;",
                  "- interpreting rank overlap or RRF score as a legal correctness judgment.", ""])

    lines.extend(["## 11. Validation and unchanged-state checks", "",
                  f"- Exact reproduction check against `retrieve()` Top-10: **{len(records) - len(rank_mismatches)}/{len(records)}** matches" + (f"; mismatches: {', '.join(rank_mismatches)}." if rank_mismatches else "; no mismatches."),
                  "- The script performs retrieval queries only; it does not call Chroma add/update/delete operations.",
                  "- It reads `eval_set.json` and chunks through the current retriever; it writes only this Markdown report.",
                  f"- Current full evaluation baseline: R@1 **{baseline_metrics['recall@1']:.4f}**, R@3 **{baseline_metrics['recall@3']:.4f}**, R@5 **{baseline_metrics['recall@5']:.4f}**, R@10 **{baseline_metrics['recall@10']:.4f}**, MRR **{baseline_metrics['mrr']:.4f}**.",
                  "- `RRF_K=60` and production retrieval behavior were not changed.", ""])
    return "\n".join(lines)


def run_analysis() -> tuple[str, int]:
    """Run the fixed-list sensitivity analysis and save its report."""
    global _CURRENT_RETRIEVER
    items = load_items()
    _CURRENT_RETRIEVER = LegalRetriever()
    records = [_prepare_query(item) for item in items]
    report = build_report(records)
    REPORT_PATH.write_text(report, encoding="utf-8")
    return report, sum(not record["reproduction_matches"] for record in records)


if __name__ == "__main__":
    try:
        _, mismatches = run_analysis()
        print(f"Analyzed answerable queries: {len(load_items())}")
        print(f"Production Top-10 reproduction mismatches: {mismatches}")
        print(f"Report written: {REPORT_PATH}")
    except Exception as error:
        print(f"RRF scoring analysis failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
