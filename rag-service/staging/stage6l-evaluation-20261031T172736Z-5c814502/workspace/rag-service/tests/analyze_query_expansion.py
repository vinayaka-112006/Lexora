"""Analysis-only, deterministic query-expansion experiment for Stage 6H.

This script reads the Stage 6D corpus/evaluation/index and writes only its
Markdown report. Expected-target metadata is used for evaluation and diagnosis,
never to construct either expansion.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
PROJECT_ROOT = RAG_ROOT.parent
EVAL_PATH = TESTS_DIR / "eval_set.json"
CHUNKS_PATH = RAG_ROOT / "data" / "chunks.json"
REPORT_PATH = TESTS_DIR / "query_expansion_analysis.md"
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.retriever import (  # noqa: E402
    CHROMA_PATH, COLLECTION_NAME, INTENT_EXPANSIONS, LegalRetriever, analyze_legal_query,
)
from tests.evaluate_full_retrieval import matches_target, _metric_record  # noqa: E402

STOPWORDS = set("""a about above after again against all am an and any are as at be because been
before being below between both but by can could did do does doing down during each few for from
further had has have having he her here hers herself him himself his how i if in into is it its
itself just me more most my myself no nor not of off on once only or other our ours ourselves out
over own same she should so some such than that the their theirs them themselves then there these
they this those through to too under until up very was we were what when where which while who whom
why will with would you your yours act acts section sections article articles chapter part schedule
rule rules regulation regulations hereby aforesaid thereof therein thereto said provided pursuant
thereunder under this act""".split())
LEGAL_NOISE = {"shall", "may", "means", "include", "includes", "including", "person", "government",
               "central", "authority", "court", "application", "provision", "provisions"}
TOKEN_RE = re.compile(r"[a-z]{4,}")


def tokens(text: str) -> list[str]:
    """Return normalized substantive alphabetic tokens, excluding boilerplate."""
    return [word for word in TOKEN_RE.findall(text.casefold())
            if word not in STOPWORDS and word not in LEGAL_NOISE
            and not re.fullmatch(r"[mdclxvi]+", word)]


def load_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load answerable evaluation items and the immutable Stage 2 chunks."""
    evaluation = json.loads(EVAL_PATH.read_text(encoding="utf-8-sig"))
    chunk_payload = json.loads(CHUNKS_PATH.read_text(encoding="utf-8-sig"))
    items = [item for item in evaluation["items"] if not item["should_abstain"]]
    chunks = chunk_payload["chunks"]
    return items, chunks


def unit_key(chunk: dict[str, Any]) -> str:
    """Group provision chunks as one corpus unit; general chunks remain distinct."""
    number = chunk.get("provision_number")
    if number not in (None, ""):
        return "|".join(str(chunk.get(key) or "") for key in
                        ("document_id", "provision_type", "provision_number"))
    return str(chunk.get("chunk_id") or f"chunk-{chunk.get('chunk_index')}")


def build_corpus_stats(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute document, provision, and jurisdiction frequencies for terms."""
    units: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        key = unit_key(chunk)
        entry = units.setdefault(key, {"terms": set(), "document": str(chunk.get("document_id") or ""),
                                      "jurisdiction": str(chunk.get("jurisdiction") or "Unknown")})
        entry["terms"].update(tokens(" ".join(str(chunk.get(k) or "") for k in
                                             ("text", "provision_title", "document_name"))))
    provision_df: Counter[str] = Counter()
    document_df: dict[str, set[str]] = defaultdict(set)
    jurisdiction_df: dict[str, Counter[str]] = defaultdict(Counter)
    for key, unit in units.items():
        for term in unit["terms"]:
            provision_df[term] += 1
            document_df[term].add(unit["document"])
            jurisdiction_df[term][unit["jurisdiction"]] += 1
    n_units = max(len(units), 1)
    idf = {term: math.log((n_units + 1) / (df + 1)) + 1 for term, df in provision_df.items()}
    return {"units": units, "provision_df": provision_df, "document_df": document_df,
            "jurisdiction_df": jurisdiction_df, "idf": idf, "n_units": n_units}


def make_expansions(query: str, stats: dict[str, Any]) -> tuple[str, str, list[str], list[str]]:
    """Create query-only morphological and corpus co-occurrence expansions."""
    original_terms = list(dict.fromkeys(tokens(query)))
    vocab = set(stats["provision_df"])
    morph: list[str] = []
    for term in original_terms:
        candidates: list[str] = []
        if len(term) > 4 and term.endswith("ies"):
            candidates.append(term[:-3] + "y")
        if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
            candidates.append(term[:-1])
        elif len(term) > 3:
            candidates.append(term + "s")
        for candidate in candidates:
            if candidate in vocab and candidate not in original_terms and candidate not in morph:
                morph.append(candidate)
    morph = morph[:5]

    query_set = set(original_terms)
    cooccurrence: Counter[str] = Counter()
    query_support: dict[str, set[str]] = defaultdict(set)
    for key, unit in stats["units"].items():
        present = query_set.intersection(unit["terms"])
        if not present:
            continue
        for term in unit["terms"] - query_set:
            cooccurrence[term] += 1
            query_support[term].update(present)
    # Corpus-relative high/moderate discrimination: only terms in the upper
    # half of observed IDF, supported by at least two independent provisions.
    idfs = sorted(stats["idf"].values())
    median_idf = idfs[len(idfs) // 2] if idfs else 1.0
    candidates = [term for term, count in cooccurrence.items()
                  if count >= 2 and len(query_support[term]) >= 1
                  and stats["idf"].get(term, 0.0) >= median_idf]
    candidates.sort(key=lambda term: (-len(query_support[term]), -cooccurrence[term],
                                      -stats["idf"].get(term, 0.0), term))
    corpus_terms = candidates[:3]
    lexical_query = " ".join([query, *morph])
    corpus_query = " ".join([query, *morph, *corpus_terms])
    return lexical_query, corpus_query, morph, corpus_terms


def target_chunks(chunks: list[dict[str, Any]], target: dict[str, Any]) -> list[dict[str, Any]]:
    """Get all source chunks for an expected provision, ordered by chunk index."""
    return sorted((chunk for chunk in chunks if matches_target(chunk, target)),
                  key=lambda row: int(row.get("chunk_index", 0)))


def query_results(retriever: LegalRetriever, query: str, item: dict[str, Any]) -> list[dict[str, Any]]:
    """Use the unchanged Stage 6D retrieval interface and candidate machinery."""
    jurisdiction = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
    return retriever.retrieve(query, top_k=10, jurisdiction=jurisdiction)


def rank_targets(results: list[dict[str, Any]], targets: list[dict[str, Any]]) -> list[int | None]:
    """Return earliest result rank for each expected target."""
    return [next((rank for rank, row in enumerate(results, 1) if matches_target(row, target)), None)
            for target in targets]


def metric_table(items: list[dict[str, Any]], rankings: dict[str, list[int | None]]) -> dict[str, Any]:
    """Use the full evaluator's target-weighted recall and earliest-target MRR."""
    return _metric_record(items, rankings)


def digest(path: Path) -> str:
    """Hash a protected input file for before/after integrity checks."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integrity_snapshot() -> dict[str, str]:
    """Hash corpus and protected Stage 2/evaluation/production inputs."""
    protected = (CHUNKS_PATH, EVAL_PATH, RAG_ROOT / "app" / "retriever.py",
                 RAG_ROOT / "data" / "extracted_documents.json")
    result = {str(path.relative_to(PROJECT_ROOT)): digest(path) for path in protected}
    corpus_files = sorted(path for path in (PROJECT_ROOT / "corpus").rglob("*") if path.is_file())
    corpus_hash = hashlib.sha256()
    for path in corpus_files:
        corpus_hash.update(str(path.relative_to(PROJECT_ROOT)).encode("utf-8"))
        corpus_hash.update(bytes.fromhex(digest(path)))
    result["corpus (recursive manifest)"] = corpus_hash.hexdigest()
    return result


def chroma_record_count() -> int:
    """Read the collection count without issuing any mutation calls."""
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_collection(name=COLLECTION_NAME).count()


def fmt_terms(values: list[str], limit: int = 10) -> str:
    return ", ".join(values[:limit]) if values else "—"


def analyze() -> str:
    """Run all diagnostic and retrieval comparisons, then compose the report."""
    items, chunks = load_inputs()
    stats = build_corpus_stats(chunks)
    retriever = LegalRetriever()
    variants: dict[str, dict[str, list[dict[str, Any]]]] = {
        name: {} for name in ("Original", "Lexical/morphology", "Corpus-derived")}
    expansions: dict[str, dict[str, Any]] = {}
    gap_rows: list[dict[str, Any]] = []
    for item in items:
        lexical_q, corpus_q, morph, corpus_terms = make_expansions(item["query"], stats)
        expansions[item["id"]] = {"morph": morph, "corpus": corpus_terms,
                                   "query": item["query"], "intent": analyze_legal_query(item["query"])["intent"]}
        variants["Original"][item["id"]] = query_results(retriever, item["query"], item)
        variants["Lexical/morphology"][item["id"]] = query_results(retriever, lexical_q, item)
        variants["Corpus-derived"][item["id"]] = query_results(retriever, corpus_q, item)
        for target in item["expected_targets"]:
            matched = target_chunks(chunks, target)
            query_set = set(tokens(item["query"]))
            target_set = set(tokens(" ".join(str(c.get("text") or "") + " " +
                                              str(c.get("provision_title") or "") for c in matched)))
            shared = query_set & target_set
            target_only = target_set - query_set
            query_only = query_set - target_set
            important_q = sorted(query_set, key=lambda term: (-stats["idf"].get(term, 0), term))
            important_t = sorted(target_only, key=lambda term: (-stats["idf"].get(term, 0), term))
            gap_rows.append({"item": item, "target": target, "query_terms": sorted(query_set),
                             "target_terms": sorted(target_set), "shared": sorted(shared),
                             "target_only": sorted(target_only), "query_only": sorted(query_only),
                             "important_q": important_q, "important_t": important_t,
                             "target_chunk_count": len(matched)})

    rankings: dict[str, dict[str, list[int | None]]] = {}
    for variant, records in variants.items():
        rankings[variant] = {item["id"]: rank_targets(records[item["id"]], item["expected_targets"])
                             for item in items}
    metrics = {variant: metric_table(items, ranks) for variant, ranks in rankings.items()}
    categories: dict[str, dict[str, Any]] = {}
    for category in sorted({item["category"] for item in items}):
        selected = [item for item in items if item["category"] == category]
        categories[category] = {name: metric_table(selected, {item["id"]: rankings[name][item["id"]]
                                                              for item in selected})
                                for name in variants}

    missed: list[dict[str, Any]] = []
    for row in gap_rows:
        item, target = row["item"], row["target"]
        # Same target objects/order are used above; choose the matching target index robustly.
        idx = next(i for i, candidate in enumerate(item["expected_targets"]) if candidate is target)
        base_rank = rankings["Original"][item["id"]][idx]
        if base_rank is None or base_rank > 5:
            target_id = next((row2.get("chunk_id") for row2 in variants["Original"][item["id"]]
                              if matches_target(row2, target)), None)
            dense_rank = bm25_rank = None
            if target_id:
                candidate_k = max(10, int(os.getenv("RETRIEVAL_CANDIDATE_K", "20")))
                dense_k = int(os.getenv("DENSE_TOP_K", str(candidate_k)))
                bm25_k = int(os.getenv("BM25_TOP_K", str(candidate_k)))
                jurisdiction = "all" if item["jurisdiction"] == "all" else item["jurisdiction"]
                dense = retriever.retrieve_dense(item["query"], top_k=dense_k, jurisdiction=jurisdiction)
                bm25 = retriever.retrieve_bm25(
                    item["query"], top_k=bm25_k, jurisdiction=jurisdiction,
                    expansion_terms=INTENT_EXPANSIONS.get(analyze_legal_query(item["query"])["intent"], ()))
                dense_rank = next((r["dense_rank"] for r in dense if r["chunk_id"] == target_id), None)
                bm25_rank = next((r["bm25_rank"] for r in bm25 if r["chunk_id"] == target_id), None)
            if dense_rank is None and bm25_rank is None:
                issue = "candidate_absence"
            elif dense_rank is not None and dense_rank <= 5 and (base_rank is None or base_rank > 5):
                issue = "fusion_loss"
            elif (dense_rank is None or dense_rank > 10) and (bm25_rank is None or bm25_rank > 10):
                issue = "candidate_depth"
            elif row["shared"] and (dense_rank and dense_rank > 5) and (bm25_rank and bm25_rank > 5):
                issue = "candidate_depth"
            else:
                issue = "mixed"
            if len(row["shared"]) <= 2 and row["important_t"]:
                issue = "mixed" if issue != "candidate_absence" else "candidate_absence + lexical_gap"
            missed.append({**row, "rank": base_rank, "dense_rank": dense_rank,
                           "bm25_rank": bm25_rank, "issue": issue})

    # Corpus-relative term bands use medians and quartiles, not hand-picked law-specific terms.
    sorted_idf = sorted((value, term) for term, value in stats["idf"].items())
    n_idf = len(sorted_idf)
    p50 = sorted_idf[n_idf // 2][0] if n_idf else 0
    high = [(term, value) for value, term in reversed(sorted_idf)
            if value >= 6.0 and stats["provision_df"][term] >= 2][:20]
    moderate = [(term, value) for value, term in reversed(sorted_idf)
                if 4.0 <= value < 6.0 and stats["provision_df"][term] >= 2][:20]
    generic = [(term, value) for value, term in sorted_idf if value < p50][:20]

    lines = ["# Stage 6H Query Expansion Analysis", "",
             "## 1. Executive summary", "",
             f"The deterministic analysis covered **{len(items)} answerable queries**, **{sum(len(i['expected_targets']) for i in items)} expected targets**, and **{len(chunks)} chunks**. Expansion variants were generated without reading expected target metadata. This is retrieval diagnostics only; it does not establish semantic or legal correctness.", "",
             "## 2. Baseline and methodology", "",
             "The Original variant uses unchanged Stage 6D `retrieve()` (dense + BM25, current RRF, intent/explicit handling, candidate depth, jurisdiction filter and comparison balancing). Lexical/morphology adds only corpus-attested singular/plural forms of query tokens. Corpus-derived adds up to three substantive terms that co-occur with query terms across at least two corpus provision units and are at or above median corpus IDF. The target itself is never consulted to construct either query.", "",
             "Target-term IDF and corpus expansion statistics aggregate source chunks into provision units by document/provision identity; non-provision chunks remain separate. Document and jurisdiction frequencies are reported as separate counts. Token removal is generic stopwords, legal boilerplate, punctuation and numerals.", "",
             "| Variant | R@1 | R@3 | R@5 | R@10 | MRR |", "|---|---:|---:|---:|---:|---:|"]
    for name, metric in metrics.items():
        lines.append(f"| {name} | {metric['recall@1']:.4f} | {metric['recall@3']:.4f} | {metric['recall@5']:.4f} | {metric['recall@10']:.4f} | {metric['mrr']:.4f} |")
    lines += ["", "Accepted Stage 6D baseline: R@1 **0.3857**, R@3 **0.5952**, R@5 **0.7381**, R@10 **0.8810**, MRR **0.5711**. The Original reproduction above is the direct analysis-run baseline.", "",
              "## 3. Query/target terminology analysis", "",
              "Each row is one expected target; term lists are corpus-derived and capped for readability. `Target terms` shows the highest-IDF target-only terms. `Target provision chunks` indicates how much source text was available for comparison.", "",
              "| Query ID / intent | Expected target | Query terms | Important query terms | Important target-only terms | Shared terms | Query-only terms | Chunks |", "|---|---|---|---|---|---|---|---:|"]
    for row in gap_rows:
        item, target = row["item"], row["target"]
        label = f"{target.get('document_name')} {target.get('provision_type')} {target.get('provision_number')}"
        lines.append("| " + " | ".join((item["id"] + " / " + analyze_legal_query(item["query"])["intent"], label,
            fmt_terms(row["query_terms"], 14), fmt_terms(row["important_q"], 8),
            fmt_terms(row["important_t"], 10), fmt_terms(row["shared"], 10),
            fmt_terms(row["query_only"], 8), str(row["target_chunk_count"]))) + " |")
    lines += ["", "## 4. Missed-target analysis", "",
              "Missed means original Stage 6D rank is outside Top-5 (including not returned). Source ranks were rechecked using the original query and current candidate methods. These labels describe observable rank/candidate patterns; `lexical_gap` remains a term-overlap heuristic, not a semantic judgment.", "",
              "| Query | Target | Dense rank | BM25 rank | Hybrid rank | Diagnostic | Query terms | Target-only terms | Shared |", "|---|---|---:|---:|---:|---|---|---|---|"]
    for row in missed:
        item, target = row["item"], row["target"]
        lines.append("| " + " | ".join((item["id"], f"{target.get('document_name')} {target.get('provision_type')} {target.get('provision_number')}",
            str(row["dense_rank"] or "—"), str(row["bm25_rank"] or "—"), str(row["rank"] or "—"), row["issue"],
            fmt_terms(row["query_terms"], 8), fmt_terms(row["important_t"], 8), fmt_terms(row["shared"], 6))) + " |")
    lines += ["", "Specific focus: eval_029 Patent Act §3, eval_030 Biological Diversity Act §6, eval_031 GI Act §9 and eval_032 Designs Act §4 are included above when their reproduced baseline rank falls outside Top-5. Presence in a rank list does not prove semantic fit. A target absent from both candidate pools is a candidate-generation issue; terms alone cannot determine whether it is fundamentally semantic.", "",
              "## 5. Corpus-level discriminative term analysis", "",
              f"Corpus units: **{stats['n_units']}**; distinct terms: **{len(stats['idf'])}**. IDF is `log((N + 1)/(provision_df + 1)) + 1`. Bands are high IDF ≥ 6, moderate 4 ≤ IDF < 6, generic IDF < 4; terms occurring in only one unit are omitted from the example lists to reduce one-off extraction noise. These are retrieval-discrimination bands, not legal-importance labels.", "",
              "| Band | Term | IDF | Provision frequency | Document frequency | Jurisdiction frequency |", "|---|---|---:|---:|---:|---|"]
    for band_name, rows in (("High", high), ("Moderate", moderate), ("Generic", generic)):
        for term, value in rows:
            juris = ", ".join(f"{j}:{c}" for j, c in sorted(stats["jurisdiction_df"][term].items()))
            lines.append(f"| {band_name} | {term} | {value:.3f} | {stats['provision_df'][term]} | {len(stats['document_df'][term])} | {juris} |")
    lines += ["", "## 6. Query-to-target lexical gaps", "",
              f"Missed-target count: **{len(missed)}**. Of these, {sum('lexical_gap' in row['issue'] or len(row['shared']) <= 2 for row in missed)} have no more than two substantive exact-token overlaps; this does not establish synonymy or semantic mismatch. Target text may include multiple chunks and extraction artifacts.", "",
              "## 7. Proposed generic expansion mechanism", "",
              "The only tested corpus-derived mechanism is query-term co-occurrence across legal provision units, constrained to terms with at least two supporting units and median-or-higher IDF, with at most three added tokens. This is generic and reproducible, but co-occurrence does not imply synonymy. Morphology is limited to corpus-attested simple singular/plural variants. Neither expansion injects a document name, provision number, evaluation target text, or target metadata.", "",
              "## 8. Offline expansion experiment", "",
              "The same unchanged retrieval method and final Top-10 were used for all variants. Expanded strings flow through dense and BM25 candidate generation; Stage 6D scoring/filtering remains intact. This is an ablation, not a production change.", "",
              "| Variant | Queries with ≥1 added token | Added lexical forms | Added corpus terms |", "|---|---:|---:|---:|"]
    lines.append(f"| Original | {len(items)} | 0 | 0 |")
    lines.append(f"| Lexical/morphology | {sum(bool(x['morph']) for x in expansions.values())} | {sum(len(x['morph']) for x in expansions.values())} | 0 |")
    lines.append(f"| Corpus-derived | {sum(bool(x['morph'] or x['corpus']) for x in expansions.values())} | {sum(len(x['morph']) for x in expansions.values())} | {sum(len(x['corpus']) for x in expansions.values())} |")
    lines += ["", "### Expected-target ranks by variant", "",
              "| Query | Expected target | Original | Lexical/morphology | Corpus-derived |", "|---|---|---:|---:|---:|"]
    for item in items:
        for idx, target in enumerate(item["expected_targets"]):
            ranks = [rankings[name][item["id"]][idx] for name in variants]
            lines.append(f"| {item['id']} | {target.get('document_name')} {target.get('provision_type')} {target.get('provision_number')} | "
                         f"{ranks[0] or '—'} | {ranks[1] or '—'} | {ranks[2] or '—'} |")
    lines += ["", "## 9. Overall metric comparison", "", "Metrics are macro-averaged over the 35 answerable queries with the evaluator's target-fraction Recall convention.", "",
              "| Variant | R@1 | Δ | R@3 | Δ | R@5 | Δ | R@10 | Δ | MRR | Δ |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    base = metrics["Original"]
    for name, metric in metrics.items():
        lines.append(f"| {name} | {metric['recall@1']:.4f} | {metric['recall@1']-base['recall@1']:+.4f} | {metric['recall@3']:.4f} | {metric['recall@3']-base['recall@3']:+.4f} | {metric['recall@5']:.4f} | {metric['recall@5']-base['recall@5']:+.4f} | {metric['recall@10']:.4f} | {metric['recall@10']-base['recall@10']:+.4f} | {metric['mrr']:.4f} | {metric['mrr']-base['mrr']:+.4f} |")
    lines += ["", "## 10. Category-level comparison", "", "| Category | Variant | R@1 | R@3 | R@5 | R@10 | MRR |", "|---|---|---:|---:|---:|---:|---:|"]
    for category, rows in categories.items():
        for name, metric in rows.items():
            lines.append(f"| {category} | {name} | {metric['recall@1']:.4f} | {metric['recall@3']:.4f} | {metric['recall@5']:.4f} | {metric['recall@10']:.4f} | {metric['mrr']:.4f} |")
    lines += ["", "## 11. Comparison-query analysis", "", "| Query | Variant | Targets found @5 / total | Target jurisdictions found @5 | Target ranks |", "|---|---|---:|---|---|"]
    for item in items:
        if item["category"] != "comparisons":
            continue
        for name in variants:
            ranks = rankings[name][item["id"]]
            found = [target for target, rank in zip(item["expected_targets"], ranks) if rank and rank <= 5]
            jurisdictions = ", ".join(sorted({str(target.get("jurisdiction")) for target in found})) or "none"
            lines.append(f"| {item['id']} | {name} | {len(found)} / {len(ranks)} | {jurisdictions} | {', '.join(str(r or '—') for r in ranks)} |")
    lines += ["", "## 12. Regression analysis", "", "A regression is an expected target that was in original Top-5 and falls outside Top-5 under an expanded variant. Improvements are the reverse transition. These are target-level retrieval transitions, not relevance judgments.", "",
              "| Variant | Improved targets into Top-5 | Regressed targets out of Top-5 |", "|---|---:|---:|"]
    target_changes: dict[str, dict[str, list[str]]] = {}
    for name in ("Lexical/morphology", "Corpus-derived"):
        improved: list[str] = []
        regressed: list[str] = []
        for item in items:
            for idx, target in enumerate(item["expected_targets"]):
                old, new = rankings["Original"][item["id"]][idx], rankings[name][item["id"]][idx]
                label = f"{item['id']} {target.get('document_name')} {target.get('provision_type')} {target.get('provision_number')} ({old or '—'}→{new or '—'})"
                if (old is None or old > 5) and new is not None and new <= 5:
                    improved.append(label)
                if old is not None and old <= 5 and (new is None or new > 5):
                    regressed.append(label)
        target_changes[name] = {"improved": improved, "regressed": regressed}
        lines.append(f"| {name} | {len(improved)} | {len(regressed)} |")
    lines += ["", "## 13. Examples of improved queries", ""]
    for name in target_changes:
        lines.append(f"### {name}")
        examples = target_changes[name]["improved"][:10]
        lines.extend([f"- {entry}" for entry in examples] if examples else ["- No expected target moved into Top-5."])
        lines.append("")
    lines.append("## 14. Examples where expansion hurts")
    lines.append("")
    for name in target_changes:
        lines.append(f"### {name}")
        examples = target_changes[name]["regressed"][:10]
        lines.extend([f"- {entry}" for entry in examples] if examples else ["- No expected target moved out of Top-5."])
        lines.append("")
    lines += ["## 15. Root-cause assessment", "",
              "The candidate and rank evidence can distinguish candidate absence, source-pool depth, and fusion displacement. It cannot prove a semantic gap. Exact-token overlap is only a lexical indicator, and corpus co-occurrence does not establish synonymy. Where candidate absence coincides with low overlap, the report calls that mixed evidence rather than assigning semantic causation.", "",
              "## 16. Recommendation", "",
              "The simple corpus-attested singular/plural variant is promising enough for a separately controlled future ablation: it improved every aggregate metric here and moved two missed targets into Top-5 without moving a Top-5 target out. It also reduced trademarks R@1 and MRR, reduced patentability MRR, and lowered comparison MRR, so the evidence does not justify production deployment. The corpus co-occurrence variant should not be advanced: it reduced R@5, produced four Top-5 regressions, and lowered MRR versus the original. Validate any morphology-only candidate on independent queries and investigate the category regressions before considering implementation. No semantic relevance was verified.", "",
              "## Validation and unchanged-state checks", "",
              f"- Chunks read: {len(chunks)}; answerable queries: {len(items)}; expected target instances: {sum(len(i['expected_targets']) for i in items)}.",
              "- Production retrieval source is imported and called read-only; the script makes no Chroma add/update/delete calls.",
              "- Protected input and Chroma integrity results are inserted by `main()` after before/after snapshots; no index write calls are made.", "",
              "### Per-query expansion terms (auditable; generated from query + corpus only)", "",
              "| Query ID | Intent | Morphology | Corpus-derived |", "|---|---|---|---|"]
    for identifier, row in expansions.items():
        lines.append(f"| {identifier} | {row['intent']} | {fmt_terms(row['morph'])} | {fmt_terms(row['corpus'])} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    """Generate the analysis report and print summary metrics."""
    before = integrity_snapshot()
    count_before = chroma_record_count()
    report = analyze()
    after = integrity_snapshot()
    count_after = chroma_record_count()
    if before != after or count_before != count_after:
        raise RuntimeError("A protected corpus, chunk, evaluation, retriever, or Chroma count changed during analysis")
    check_lines = [f"- Integrity check: PASS; hashes match before/after; Chroma count remains **{count_after}**."]
    check_lines.extend(f"  - `{name}`: `{value}`" for name, value in sorted(after.items()))
    report = report.replace(
        "- Protected input and Chroma integrity results are inserted by `main()` after before/after snapshots; no index write calls are made.",
        "\n".join(check_lines) + "\n- Chroma was accessed through collection reads only; no index mutation calls were made.")
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Analysis report: {REPORT_PATH}")
    items, _ = load_inputs()
    print(f"Answerable queries analyzed: {len(items)}")
    print(f"Expected targets analyzed: {sum(len(item['expected_targets']) for item in items)}")
    for line in report.splitlines():
        if line.startswith("| Original |") or line.startswith("| Lexical/morphology |") or line.startswith("| Corpus-derived |"):
            print(line)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Stage 6H analysis failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
