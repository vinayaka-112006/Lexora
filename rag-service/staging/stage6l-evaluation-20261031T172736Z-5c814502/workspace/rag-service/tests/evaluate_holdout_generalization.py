"""Compare Stage 6D and Stage 6J retrieval on the frozen Stage 6K holdout set."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
PROJECT_ROOT = RAG_ROOT.parent
HOLDOUT_PATH = TESTS_DIR / "holdout_eval_set.json"
REPORT_PATH = TESTS_DIR / "holdout_generalization_results.md"
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.retriever import LegalRetriever, analyze_legal_query  # noqa: E402

CUTOFFS = (1, 3, 5, 10)
IDENTITY_FIELDS = ("document_id", "document_name", "jurisdiction", "provision_type", "provision_number")
METRICS = ("recall@1", "recall@3", "recall@5", "recall@10", "mrr")


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _matches(row: dict[str, Any], target: dict[str, Any]) -> bool:
    return all(_norm(row.get(field)) == _norm(target.get(field)) for field in IDENTITY_FIELDS)


def _rank(results: list[dict[str, Any]], target: dict[str, Any]) -> int | None:
    return next((rank for rank, row in enumerate(results, 1) if _matches(row, target)), None)


def _rankings(items: list[dict[str, Any]], results: dict[str, list[dict[str, Any]]]) -> dict[str, list[int | None]]:
    return {item["id"]: [_rank(results[item["id"]], target) for target in item["expected_targets"]]
            for item in items if not item["should_abstain"]}


def _metrics(items: list[dict[str, Any]], rankings: dict[str, list[int | None]]) -> dict[str, Any]:
    if not items:
        return {"n": 0, **{name: 0.0 for name in METRICS}}
    totals = {cutoff: 0.0 for cutoff in CUTOFFS}
    reciprocal: list[float] = []
    for item in items:
        ranks = rankings[item["id"]]
        for cutoff in CUTOFFS:
            totals[cutoff] += sum(rank is not None and rank <= cutoff for rank in ranks) / len(ranks)
        found = [rank for rank in ranks if rank is not None]
        reciprocal.append(1 / min(found) if found else 0.0)
    count = len(items)
    return {"n": count, **{f"recall@{cutoff}": round(totals[cutoff] / count, 4) for cutoff in CUTOFFS},
            "mrr": round(sum(reciprocal) / count, 4)}


def _mode(retriever: LegalRetriever, items: list[dict[str, Any]], enabled: bool) -> dict[str, Any]:
    os.environ["MORPHOLOGY_EXPANSION_ENABLED"] = "true" if enabled else "false"
    first: dict[str, list[dict[str, Any]]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    for item in items:
        jurisdiction = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
        first[item["id"]] = retriever.retrieve(item["query"], top_k=10, jurisdiction=jurisdiction)
        diagnostics[item["id"]] = dict(retriever.last_retrieval_debug)
    repeated: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        jurisdiction = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
        repeated[item["id"]] = retriever.retrieve(item["query"], top_k=10, jurisdiction=jurisdiction)
    mismatches = [item["id"] for item in items if
                  [row.get("chunk_id") for row in first[item["id"]]] !=
                  [row.get("chunk_id") for row in repeated[item["id"]]]]
    eligible = [item for item in items if not item["should_abstain"]]
    rankings = _rankings(eligible, first)
    category_metrics = {
        category: _metrics([item for item in eligible if item["category"] == category], rankings)
        for category in sorted({item["category"] for item in eligible})
    }
    query_type_metrics = {
        query_type: _metrics([item for item in eligible if item["query_type"] == query_type], rankings)
        for query_type in sorted({item["query_type"] for item in eligible})
    }
    jurisdiction_violations: list[str] = []
    for item in items:
        requested = item["jurisdiction"]
        if requested in {"India", "International"} and any(
            row.get("jurisdiction") != requested for row in first[item["id"]]
        ):
            jurisdiction_violations.append(item["id"])
    explicit_items = [item for item in eligible if item["query_type"] == "explicit_provision"]
    explicit_top1 = sum(bool(rankings[item["id"]]) and rankings[item["id"]][0] == 1
                        for item in explicit_items)
    comparison_items = [item for item in eligible if item["query_type"] == "comparison"]
    comparison_rows = []
    for item in comparison_items:
        ranks = rankings[item["id"]]
        comparison_rows.append({
            "id": item["id"], "query": item["query"],
            "target_coverage@5": round(sum(r is not None and r <= 5 for r in ranks) / len(ranks), 4),
            "target_coverage@10": round(sum(r is not None and r <= 10 for r in ranks) / len(ranks), 4),
            "found_jurisdictions@5": sorted({row.get("jurisdiction") for row in first[item["id"]][:5]}),
            "found_jurisdictions@10": sorted({row.get("jurisdiction") for row in first[item["id"]][:10]}),
        })
    return {
        "results": first, "diagnostics": diagnostics, "rankings": rankings,
        "metrics": _metrics(eligible, rankings), "category_metrics": category_metrics,
        "query_type_metrics": query_type_metrics, "deterministic": not mismatches,
        "determinism_mismatches": mismatches, "jurisdiction_violations": jurisdiction_violations,
        "explicit_top1": {"correct": explicit_top1, "total": len(explicit_items)},
        "comparison_rows": comparison_rows,
    }


def _rank_for_target(mode: dict[str, Any], item_id: str, target: dict[str, Any]) -> int | None:
    return _rank(mode["results"][item_id], target)


def _run_regressions() -> dict[str, Any]:
    """Run the existing unit, Stage 5A.1, and 42-query regression checks after holdout runs."""
    env = os.environ.copy()
    env["MORPHOLOGY_EXPANSION_ENABLED"] = "false"
    commands = {
        "unit_tests": [sys.executable, "-B", "-m", "unittest", "discover", "-s",
                        "rag-service/tests", "-p", "test_*.py"],
        "stage_5a_1": [sys.executable, "-B", "rag-service/tests/evaluate_retrieval.py"],
        "stage_6d_42_query": [sys.executable, "-B", "rag-service/tests/evaluate_full_retrieval.py"],
    }
    outcomes = {}
    for name, command in commands.items():
        completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = completed.stdout
        metrics = re.findall(r"(?:Recall@\d+|MRR|RECALL@\d+):?\s*([0-9]+\.[0-9]+)", output)
        outcomes[name] = {"passed": completed.returncode == 0, "returncode": completed.returncode,
                          "summary": "\n".join(line for line in output.splitlines() if any(
                              marker in line for marker in ("Ran ", "OK", "Macro metrics", "Recall@", "RECALL@", "MRR:",
                                                            "Violations:", "Ranking mismatches", "Deterministic:"))),
                          "metrics": metrics}
    return outcomes


def _render_report(items: list[dict[str, Any]], baseline: dict[str, Any], morphology: dict[str, Any],
                   regressions: dict[str, Any]) -> tuple[str, str]:
    eligible = [item for item in items if not item["should_abstain"]]
    wins: list[str] = []
    baseline_wins: list[str] = []
    ties: list[str] = []
    changed_targets: list[tuple[dict[str, Any], dict[str, Any], int | None, int | None]] = []
    for item in eligible:
        branks, mranks = baseline["rankings"][item["id"]], morphology["rankings"][item["id"]]
        bfound = [rank for rank in branks if rank is not None]
        mfound = [rank for rank in mranks if rank is not None]
        bscore = 1 / min(bfound) if bfound else 0.0
        mscore = 1 / min(mfound) if mfound else 0.0
        (wins if mscore > bscore else baseline_wins if bscore > mscore else ties).append(item["id"])
        for target in item["expected_targets"]:
            brank = _rank_for_target(baseline, item["id"], target)
            mrank = _rank_for_target(morphology, item["id"], target)
            if brank != mrank:
                changed_targets.append((item, target, brank, mrank))

    important_safe = (baseline["explicit_top1"]["correct"] == morphology["explicit_top1"]["correct"]
                      and baseline["comparison_rows"] == morphology["comparison_rows"]
                      and not baseline["jurisdiction_violations"] and not morphology["jurisdiction_violations"]
                      and baseline["deterministic"] and morphology["deterministic"])
    improved_overall = all(morphology["metrics"][metric] >= baseline["metrics"][metric]
                           for metric in ("recall@1", "recall@5", "mrr"))
    category_regressions = []
    for category, bm in baseline["category_metrics"].items():
        mm = morphology["category_metrics"][category]
        if any(mm[key] < bm[key] for key in METRICS):
            category_regressions.append(category)
    regression_ok = all(record["passed"] for record in regressions.values())
    if improved_overall and important_safe and regression_ok and not category_regressions:
        status, recommendation = "PASS", "CONSIDER ENABLED"
        interpretation = "STRONG PASS: aggregate metrics are maintained or improved without category regressions or safety failures."
    elif improved_overall and important_safe and regression_ok:
        status, recommendation = "PASS", "KEEP DISABLED BY DEFAULT"
        interpretation = "PASS WITH TRADEOFF: aggregate metrics improve, but some categories regress; retain the current default and analyze those categories before any default change."
    elif important_safe and regression_ok:
        status, recommendation = "WARN", "KEEP DISABLED BY DEFAULT"
        interpretation = "WARN: results are mixed; the holdout does not justify enabling morphology globally."
    else:
        status, recommendation = "FAIL", "KEEP DISABLED BY DEFAULT"
        interpretation = "FAIL: a safety, determinism, or regression-test gate failed."

    lines = [
        "# Stage 6K Holdout / Generalization Evaluation", "",
        "## Dataset composition", "",
        f"- New queries: {len(items)}; answerable: {len(eligible)}; abstention/out-of-scope: {len(items)-len(eligible)}.",
        f"- Categories: {dict(Counter(item['category'] for item in items))}.",
        f"- Query types: {dict(Counter(item['query_type'] for item in items))}.",
        f"- Jurisdictions: {dict(Counter(item['jurisdiction'] for item in items))}.",
        "- Target provisions were resolved from existing chunks and checked against indexed Chroma records.",
        "- Query text was authored for this holdout; the existing 42-query set was not changed.", "",
        "## Stage 6D and Stage 6J results", "",
        "Stage 6D is the same production code with morphology disabled. Stage 6J uses the same set and settings with only the morphology flag enabled.", "",
        "| Metric | Stage 6D (disabled) | Stage 6J (enabled) | Delta |", "|---|---:|---:|---:|",
    ]
    for metric in METRICS:
        delta = morphology["metrics"][metric] - baseline["metrics"][metric]
        lines.append(f"| {metric} | {baseline['metrics'][metric]:.4f} | {morphology['metrics'][metric]:.4f} | {delta:+.4f} |")
    lines += ["", "## Category-level comparison", "",
              "| Category | Stage 6D (R@1/R@3/R@5/R@10/MRR) | Stage 6J (R@1/R@3/R@5/R@10/MRR) | Assessment |",
              "|---|---|---|---|"]
    for category in baseline["category_metrics"]:
        bm, mm = baseline["category_metrics"][category], morphology["category_metrics"][category]
        changed = [key for key in METRICS if bm[key] != mm[key]]
        assessment = "unchanged" if not changed else ("improved" if all(mm[k] >= bm[k] for k in METRICS) else
                    "mixed/regressed" if any(mm[k] < bm[k] for k in METRICS) else "improved")
        fmt = lambda data: " / ".join(f"{data[k]:.4f}" for k in METRICS)
        lines.append(f"| {category} | {fmt(bm)} | {fmt(mm)} | {assessment} |")
    lines += ["", "## Query-type comparison", "", "| Query type | Stage 6D | Stage 6J |", "|---|---|---|"]
    for query_type in sorted(set(baseline["query_type_metrics"]) | set(morphology["query_type_metrics"])):
        bm = baseline["query_type_metrics"].get(query_type, {"n": 0, **{k: 0 for k in METRICS}})
        mm = morphology["query_type_metrics"].get(query_type, {"n": 0, **{k: 0 for k in METRICS}})
        lines.append(f"| {query_type} (n={bm['n']}/{mm['n']}) | {', '.join(f'{k} {bm[k]:.4f}' for k in METRICS)} | {', '.join(f'{k} {mm[k]:.4f}' for k in METRICS)} |")
    lines += ["", "## Morphology wins, baseline wins, and ties", "",
              f"- Wins by query-level earliest-target reciprocal rank: morphology {len(wins)}, baseline {len(baseline_wins)}, ties {len(ties)}.",
              f"- Morphology wins: {', '.join(wins) if wins else 'none'}.",
              f"- Baseline wins: {', '.join(baseline_wins) if baseline_wins else 'none'}.",
              f"- Ties: {', '.join(ties) if ties else 'none'}.",
              "- A query is a win when its earliest expected target has a better reciprocal rank; comparisons therefore also report target coverage separately.", "",
              "## Changed target ranks", ""]
    if changed_targets:
        lines += ["| Query | Expected target | Stage 6D rank | Stage 6J rank | Morphology applied | Added terms |",
                  "|---|---|---:|---:|---|---|"]
        for item, target, brank, mrank in changed_targets:
            debug = morphology["diagnostics"][item["id"]]
            retrieval_query = str(debug.get("retrieval_query") or item["query"])
            additions = retrieval_query[len(item["query"]):].strip() if retrieval_query.startswith(item["query"]) else ""
            target_label = f"{target['document_name']} {target['provision_type']} {target['provision_number']} ({target['jurisdiction']})"
            lines.append(f"| {item['id']}: {item['query']} | {target_label} | {brank or 'not in Top 10'} | {mrank or 'not in Top 10'} | {debug.get('morphology_applied')} | {additions or '—'} |")
    else:
        lines.append("No expected target changed rank.")
    lines += ["", "## Explicit provision safety", "",
              f"- Stage 6D rank-1 accuracy: {baseline['explicit_top1']['correct']}/{baseline['explicit_top1']['total']}.",
              f"- Stage 6J rank-1 accuracy: {morphology['explicit_top1']['correct']}/{morphology['explicit_top1']['total']}.",
              "- Explicit target ranks are included in the changed-target table above when they differ.", "",
              "## Comparison-query behavior", "",
              "| Query | Stage 6D target coverage @5/@10 | Stage 6J target coverage @5/@10 | Stage 6D jurisdictions @5/@10 | Stage 6J jurisdictions @5/@10 |",
              "|---|---|---|---|---|"]
    for b_row, m_row in zip(baseline["comparison_rows"], morphology["comparison_rows"]):
        lines.append(f"| {b_row['id']}: {b_row['query']} | {b_row['target_coverage@5']:.2f}/{b_row['target_coverage@10']:.2f} | {m_row['target_coverage@5']:.2f}/{m_row['target_coverage@10']:.2f} | {b_row['found_jurisdictions@5']} / {b_row['found_jurisdictions@10']} | {m_row['found_jurisdictions@5']} / {m_row['found_jurisdictions@10']} |")
    lines += ["", "## Jurisdiction and determinism", "",
              f"- Stage 6D jurisdiction-filter violations: {len(baseline['jurisdiction_violations'])}.",
              f"- Stage 6J jurisdiction-filter violations: {len(morphology['jurisdiction_violations'])}.",
              f"- Stage 6D deterministic repeated rankings: {baseline['deterministic']} (mismatches: {baseline['determinism_mismatches']}).",
              f"- Stage 6J deterministic repeated rankings: {morphology['deterministic']} (mismatches: {morphology['determinism_mismatches']}).", "",
              "## Existing regression checks (run after holdout evaluation)", ""]
    for name, result in regressions.items():
        lines.append(f"- {name}: {'PASS' if result['passed'] else 'FAIL'} (exit {result['returncode']}).")
        if result["summary"]:
            lines.extend("  " + line for line in result["summary"].splitlines())
    lines += ["", "## Recommendation", "", interpretation, "",
              f"Stage 6J recommendation: **{recommendation}**. The production default remains unchanged (`MORPHOLOGY_EXPANSION_ENABLED=false`).", "",
              f"STAGE 6K STATUS: {status}", ""]
    return "\n".join(lines), status


def main() -> None:
    items = json.loads(HOLDOUT_PATH.read_text(encoding="utf-8-sig"))["items"]
    retriever = LegalRetriever()
    old_flag = os.environ.get("MORPHOLOGY_EXPANSION_ENABLED")
    try:
        baseline = _mode(retriever, items, enabled=False)
        morphology = _mode(retriever, items, enabled=True)
    finally:
        if old_flag is None:
            os.environ.pop("MORPHOLOGY_EXPANSION_ENABLED", None)
        else:
            os.environ["MORPHOLOGY_EXPANSION_ENABLED"] = old_flag
    print("Holdout evaluation complete; running existing regression checks now.")
    regressions = _run_regressions()
    report, status = _render_report(items, baseline, morphology, regressions)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Stage 6K status: {status}")
    print(f"Report: {REPORT_PATH}")
    print("Stage 6D metrics:", json.dumps(baseline["metrics"], sort_keys=True))
    print("Stage 6J metrics:", json.dumps(morphology["metrics"], sort_keys=True))
    print("Regression checks:", json.dumps({key: value["passed"] for key, value in regressions.items()}, sort_keys=True))
    if not all(value["passed"] for value in regressions.values()):
        raise SystemExit("One or more existing regression checks failed.")


if __name__ == "__main__":
    main()
