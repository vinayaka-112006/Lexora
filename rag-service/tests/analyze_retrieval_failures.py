"""Analyze Stage 6B retrieval misses without modifying retrieval or source data."""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.retriever import INTENT_EXPANSIONS, LegalRetriever, analyze_legal_query  # noqa: E402
from evaluate_full_retrieval import load_items, matches_target  # noqa: E402

OUTPUT_PATH = TESTS_DIR / "retrieval_failure_analysis.md"
TOP_K = 10


def _rank(rows: list[dict[str, Any]], target: dict[str, Any]) -> int | None:
    return next((index for index, row in enumerate(rows, start=1) if matches_target(row, target)), None)


def _target_record(target: dict[str, Any], dense: list[dict[str, Any]],
                   bm25: list[dict[str, Any]], hybrid: list[dict[str, Any]]) -> dict[str, Any]:
    dense_rank = _rank(dense, target)
    bm25_rank = _rank(bm25, target)
    hybrid_rank = _rank(hybrid, target)
    if dense_rank is not None and bm25_rank is not None:
        source_pattern = "both dense and BM25 candidates"
        if hybrid_rank is not None and hybrid_rank > 5:
            source_pattern += "; both present, hybrid rank below top 5"
        elif hybrid_rank is None:
            source_pattern += "; both present, absent from hybrid top 10"
    elif dense_rank is not None:
        source_pattern = "dense only in top 10"
    elif bm25_rank is not None:
        source_pattern = "BM25 only in top 10"
    else:
        source_pattern = "neither dense nor BM25 top 10"
    return {"target": target, "dense_rank": dense_rank, "bm25_rank": bm25_rank,
            "hybrid_rank": hybrid_rank, "source_pattern": source_pattern}


def _result_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["| Rank | Document | Document ID | Jurisdiction | Type | Number | Title | RRF | Dense rank | BM25 rank |",
             "|---:|---|---|---|---|---|---|---:|---:|---:|"]
    for rank, row in enumerate(rows, start=1):
        lines.append(
            f"| {rank} | {row.get('document_name') or ''} | {row.get('document_id') or ''} | "
            f"{row.get('jurisdiction') or ''} | {row.get('provision_type') or ''} | "
            f"{row.get('provision_number') or ''} | {(row.get('provision_title') or '').replace('|', '/')} | "
            f"{row.get('hybrid_score') if row.get('hybrid_score') is not None else ''} | "
            f"{row.get('dense_rank') if row.get('dense_rank') is not None else ''} | "
            f"{row.get('bm25_rank') if row.get('bm25_rank') is not None else ''} |"
        )
    return lines


def analyze() -> str:
    """Run only failed Stage 6B cases and return a detailed markdown report."""
    items = load_items()
    retriever = LegalRetriever()
    evaluated: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for item in items:
        if item["should_abstain"]:
            continue
        jurisdiction = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
        query = item["query"]
        analysis = analyze_legal_query(query)
        dense = retriever.retrieve_dense(query, top_k=TOP_K, jurisdiction=jurisdiction)
        expansions = INTENT_EXPANSIONS.get(analysis["intent"], ())
        bm25 = retriever.retrieve_bm25(query, top_k=TOP_K, jurisdiction=jurisdiction,
                                       expansion_terms=expansions)
        hybrid = retriever.retrieve(query, top_k=TOP_K, jurisdiction=jurisdiction, query_aware=True)
        targets = [_target_record(target, dense, bm25, hybrid) for target in item["expected_targets"]]
        record = {"item": item, "analysis": analysis, "dense": dense, "bm25": bm25,
                  "hybrid": hybrid, "targets": targets}
        evaluated[item["id"]] = record
        if any(target["hybrid_rank"] is None or target["hybrid_rank"] > 5 for target in targets):
            failures.append(record)

    issue_counts: Counter[str] = Counter()
    for record in failures:
        for target in record["targets"]:
            if target["hybrid_rank"] is None or target["hybrid_rank"] > 5:
                issue_counts[target["source_pattern"]] += 1

    lines: list[str] = [
        "# Stage 6C Retrieval Failure Analysis", "",
        "## 1. Executive summary", "",
        f"Analyzed {len(failures)} non-abstention queries with at least one expected target missing from hybrid top 5 or found only at ranks 6-10. "
        "Dense, BM25, and hybrid rankings were generated through the existing retriever methods. "
        "This is diagnostic analysis only; observations do not establish legal correctness.", "",
        "Stage 6B reference metrics: Recall@1 0.4000; Recall@3 0.4952; Recall@5 0.7095; Recall@10 0.8381; MRR 0.5501.", "",
        "## 2. Overall failure count", "",
        f"- Failed queries (one or more expected targets outside top 5): **{len(failures)} / {sum(not x['should_abstain'] for x in items)}**.",
        f"- Failed expected-target instances by candidate pattern: {dict(issue_counts)}.", "",
        "## 3. Failure table", "",
        "| ID | Category | Jurisdiction | Intent | Query | Expected targets and hybrid ranks |",
        "|---|---|---|---|---|---|",
    ]
    for record in failures:
        item = record["item"]
        target_summary = "<br>".join(
            f"{target['target'].get('document_name')} {target['target'].get('provision_type')} "
            f"{target['target'].get('provision_number')}: rank {target['hybrid_rank']} "
            f"(R1={target['hybrid_rank'] == 1}, R3={target['hybrid_rank'] is not None and target['hybrid_rank'] <= 3}, "
            f"R5={target['hybrid_rank'] is not None and target['hybrid_rank'] <= 5}, "
            f"R10={target['hybrid_rank'] is not None and target['hybrid_rank'] <= 10})"
            for target in record["targets"]
        )
        lines.append(f"| {item['id']} | {item['category']} | {item['jurisdiction']} | {item['intent']} | {item['query']} | {target_summary} |")

    lines.extend(["", "### Per-failure target ranks and top-10 retrieved results", ""])
    for record in failures:
        item = record["item"]
        lines.append(f"#### {item['id']} ({item['category']})")
        lines.append(f"Query: {item['query']}  ")
        lines.append(f"Jurisdiction: {item['jurisdiction']}; intent: {item['intent']}.")
        for target in record["targets"]:
            t = target["target"]
            rank = target["hybrid_rank"]
            lines.append(
                f"- Expected {t.get('document_name')} ({t.get('document_id')}), {t.get('provision_type')} "
                f"{t.get('provision_number')} ({t.get('provision_title')}); rank={rank}; "
                f"top1={rank == 1}; top3={rank is not None and rank <= 3}; "
                f"top5={rank is not None and rank <= 5}; top10={rank is not None and rank <= 10}; "
                f"dense={target['dense_rank']}; BM25={target['bm25_rank']}; {target['source_pattern']}."
            )
        lines.append("Top 10:")
        lines.extend(_result_table(record["hybrid"]))
        lines.append("")
    lines.extend(["", "## 4. International treaty analysis", ""])
    treaty_records = [r for r in failures if r["item"]["category"] != "comparisons" and (r["item"]["category"] == "international_treaties" or any(t["target"].get("jurisdiction") == "International" for t in r["targets"]))]
    if not treaty_records:
        lines.append("No international-treaty failures were found in the failure set.")
    for record in treaty_records:
        item = record["item"]
        lines.append(f"### {item['id']}: {item['query']}")
        for target in record["targets"]:
            t = target["target"]
            article = t.get("provision_number")
            overlap = "explicit article number in query" if f"article {article}".casefold() in item["query"].casefold() else "no explicit expected article number in query"
            title = str(t.get("provision_title") or "")
            title_terms = [w for w in title.casefold().split() if len(w) > 3]
            query_terms = set(item["query"].casefold().split())
            overlap_terms = sorted(set(title_terms) & query_terms)
            lines.append(f"- Expected {t.get('document_name')} Article {article}; document name occurs in query: {t.get('document_name','').casefold() in item['query'].casefold()}; {overlap}; title/query token overlap: {overlap_terms or 'none'}.")
            lines.append(f"  Dense rank={target['dense_rank']}; BM25 rank={target['bm25_rank']}; hybrid rank={target['hybrid_rank']}; pattern: {target['source_pattern']}.")
        lines.append("- Retrieved top 10:")
        lines.extend(_result_table(record["hybrid"]))
        lines.append("")

    lines.extend(["## 5. Patent procedure analysis", ""])
    procedure_records = [r for r in failures if r["item"]["category"] == "patent_procedure"]
    if not procedure_records:
        lines.append("No patent-procedure failures were found in the failure set.")
    for record in procedure_records:
        item = record["item"]
        lines.append(f"### {item['id']}: {item['query']}")
        for target in record["targets"]:
            t = target["target"]
            lines.append(f"- Expected Section {t.get('provision_number')} ({t.get('provision_title')}); dense={target['dense_rank']}, BM25={target['bm25_rank']}, hybrid={target['hybrid_rank']}; {target['source_pattern']}.")
        lines.append("- Top 10 results:")
        lines.extend(_result_table(record["hybrid"]))
        lines.append("")

    lines.extend(["## 6. Ayurveda / regulatory analysis", ""])
    ayurveda_records = [r for r in failures if r["item"]["category"] == "ayurveda_food_regulatory"]
    if not ayurveda_records:
        lines.append("No Ayurveda/regulatory failures were found in the failure set.")
    for record in ayurveda_records:
        item = record["item"]
        lines.append(f"### {item['id']}: {item['query']}")
        for target in record["targets"]:
            t = target["target"]
            lines.append(f"- Expected {t.get('document_name')} Section {t.get('provision_number')} ({t.get('provision_title')}); dense={target['dense_rank']}, BM25={target['bm25_rank']}, hybrid={target['hybrid_rank']}; {target['source_pattern']}.")
        lines.append("- Top 10 results:")
        lines.extend(_result_table(record["hybrid"]))
        lines.append("")

    lines.extend(["## 7. Comparison analysis", ""])
    comparison_records = [evaluated[item["id"]] for item in items if item["category"] == "comparisons" and not item["should_abstain"]]
    for record in comparison_records:
        item = record["item"]
        dist5 = Counter(row.get("jurisdiction", "unknown") for row in record["hybrid"][:5])
        dist10 = Counter(row.get("jurisdiction", "unknown") for row in record["hybrid"][:10])
        lines.append(f"### {item['id']}: {item['query']}")
        lines.append(f"- Jurisdiction distribution: top 5 {dict(dist5)}; top 10 {dict(dist10)}.")
        for target in record["targets"]:
            t = target["target"]
            lines.append(f"- Expected {t.get('jurisdiction')} {t.get('document_name')} {t.get('provision_type')} {t.get('provision_number')}: hybrid rank {target['hybrid_rank']}; dense {target['dense_rank']}; BM25 {target['bm25_rank']} ({target['source_pattern']}).")
        lines.append("- Full top 10 results:")
        lines.extend(_result_table(record["hybrid"]))
        lines.append("")

    lines.extend(["## 8. Dense vs BM25 vs hybrid analysis", "",
                  "Target ranks below are 1-based ranks within each source's top 10. `None` means the target was not present in that candidate list.", "",
                  "| ID | Expected target | Dense | BM25 | Hybrid | Observable candidate pattern |",
                  "|---|---|---:|---:|---:|---|"])
    for record in failures:
        for target in record["targets"]:
            if target["hybrid_rank"] is None or target["hybrid_rank"] > 5:
                t = target["target"]
                label = f"{t.get('document_name')} {t.get('provision_type')} {t.get('provision_number')}"
                lines.append(f"| {record['item']['id']} | {label} | {target['dense_rank']} | {target['bm25_rank']} | {target['hybrid_rank']} | {target['source_pattern']} |")
    lines.extend(["", "Interpretation is limited to returned ranks: a target in both dense and BM25 top 10 but below hybrid top 5 is consistent with fusion/ranking competition; presence in only one candidate list indicates source asymmetry; absence from both top 10 means this run does not show either source retrieving it strongly. These patterns do not prove the underlying cause.", ""])

    lines.extend(["## 9. Common failure patterns", ""])
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in failures:
        by_category[record["item"]["category"]].append(record)
    for category in ("international_treaties", "patent_procedure", "ayurveda_food_regulatory", "comparisons"):
        records = by_category.get(category, [])
        if records:
            ids = ", ".join(r["item"]["id"] for r in records)
            lines.append(f"- **{category}:** failures {ids}.")
            if category == "international_treaties":
                lines.append("  - Observed: treaty documents are often present among top results while requested articles are at ranks 6-7 or absent. PCT Article 11 is BM25 rank 3, absent from dense top 10, and hybrid rank 6 while other PCT provisions receive both signals. Nagoya Article 1 is BM25-only at rank 6 and hybrid rank 7. Madrid Protocol Article 4 is dense-only at rank 8 and absent from hybrid top 10 despite multiple Madrid provisions in results. These indicate provision-level misses and source asymmetry; Article numbers are absent from those queries, so an exact-reference boost is unavailable. The observation does not prove semantic terminology mismatch.")
            elif category == "patent_procedure":
                lines.append("  - Observed: eval_009 Section 10 is absent from both dense and BM25 top 10. Other Patent Act sections and Patent Rules chunks appear, so the document family is retrieved but the expected provision is not a strong candidate in this run. The query wording ('what information belongs in a patent specification') differs from the provision title ('Contents of specifications'); terminology mismatch is plausible, not proven.")
            elif category == "ayurveda_food_regulatory":
                lines.append("  - Observed: eval_023 Section 12 is dense rank 1, absent from BM25 top 10, and hybrid rank 6; all top 10 results are from the same regulation document. The title uses 'Labelling' while the query uses 'labeling', a plausible lexical mismatch. The rank drop is consistent with single-source RRF competition against provisions with both dense and BM25 ranks.")
            elif category == "comparisons":
                lines.append("  - Observed: both jurisdictions appear in each top 10, but expected provisions are often missing. Eval_030 has only International results in top 5 and one India result in top 10, which is not the expected Biological Diversity Act Section 6. In eval_029, TRIPS Article 27 is BM25 rank 1 while Patent Act Section 3 is absent from both candidate top 10s. This is target-level coverage loss, not a jurisdiction-filter violation; the results do not prove why candidates were missed.")
    generic = [r for r in failures if r["analysis"].get("explicit_provision") is None]
    lines.append(f"- **Queries without explicit Section/Article reference:** {len(generic)} of {len(failures)} failure queries lack an explicit provision reference; exact-reference boosts therefore do not apply to these queries.")
    rank_6_10 = [t for r in failures for t in r["targets"] if t["hybrid_rank"] is not None and 6 <= t["hybrid_rank"] <= 10]
    absent = [t for r in failures for t in r["targets"] if t["hybrid_rank"] is None]
    lines.append(f"- **Expected target at ranks 6-10:** {len(rank_6_10)} target instance(s).")
    lines.append(f"- **Expected target absent from hybrid top 10:** {len(absent)} target instance(s).")
    lines.append("- **Jurisdiction ranking:** comparison top-5/top-10 distributions are reported per query above; targets missing despite both jurisdictions appearing should be inspected as provision-ranking misses, not assumed jurisdiction-filter failures.")
    lines.append("- **BM25 weakness / dense weakness / RRF competition:** consult the source ranks table; no cause is assigned where candidate ranks do not distinguish these possibilities.")
    lines.append("- **Query-intent, expansion, or terminology mismatch:** only surface term overlap and existing ranks are observable here. The report does not infer semantic mismatch solely from a miss. Eval_029 and eval_032 contain literal question marks where apostrophes appear intended; those evaluation-set strings were left unchanged.")

    lines.extend(["", "## 10. Recommended general improvements (not implemented)", "",
                  "1. Evaluate broader dense and BM25 candidate pools before fusion, then measure whether relevant targets are recovered without adding provision-specific boosts.",
                  "2. Test general legal-domain synonym/phrase expansion against a held-out set, especially procedural verbs and regulatory terms; preserve the original query and compare ablations.",
                  "3. Audit chunk boundaries and provision metadata for provisions with low target retrieval, without rewriting source text.",
                  "4. Run retrieval ablations (dense-only, BM25-only, RRF) on the same fixed set to quantify the contribution of each stage.",
                  "5. For comparison queries, evaluate target coverage by jurisdiction separately and test general diversity strategies without assuming equivalence between legal systems.",
                  "6. Add query-level examples and confidence intervals or per-query reporting to avoid over-interpreting small category samples.", "",
                  "No retrieval, ranking, corpus, chunk, index, or evaluation-set changes were made by this analysis script.", ""])
    return "\n".join(lines)


def main() -> None:
    report = analyze()
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    failed_count = sum(1 for line in report.splitlines() if line.startswith("| eval_") and " | " in line)
    print(f"Wrote analysis report: {OUTPUT_PATH}")
    print(f"Failure-table target rows written: {failed_count}")


if __name__ == "__main__":
    main()



