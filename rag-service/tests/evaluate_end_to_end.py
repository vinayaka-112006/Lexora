"""Run the existing RAG answer pipeline over the Stage 6A 42-query set."""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

TESTS_DIR = Path(__file__).resolve().parent
RAG_ROOT = TESTS_DIR.parent
PROJECT_ROOT = RAG_ROOT.parent
EVAL_PATH = TESTS_DIR / "eval_set.json"
REPORT_PATH = TESTS_DIR / "end_to_end_evaluation_results.md"
DATA_PATH = TESTS_DIR / "end_to_end_evaluation_results.json"
TEMPLATE_PATH = TESTS_DIR / "end_to_end_review_template.md"
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from app.citation_validator import validate_citations  # noqa: E402
from app.claim_verifier import verify_claims  # noqa: E402
from app.confidence_scorer import apply_confidence_decision, score_confidence  # noqa: E402
from app.llm_client import OllamaClient  # noqa: E402
from app.main import _generate_grounded_answer, build_rag_result  # noqa: E402
from app.retriever import LegalRetriever, analyze_legal_query, get_top_k  # noqa: E402
from evaluate_full_retrieval import (  # noqa: E402
    _metric_record,
    _target_rankings,
    evaluate as evaluate_retrieval,
    load_items,
    matches_target,
)

STAGE_6D_BASELINE = {
    "recall@1": 0.3857,
    "recall@3": 0.5952,
    "recall@5": 0.7381,
    "recall@10": 0.8810,
    "mrr": 0.5711,
}


def _load_project_env(dotenv_path: Path = PROJECT_ROOT / ".env") -> bool:
    """Load this project's environment file without printing its values."""
    return load_dotenv(dotenv_path=dotenv_path, override=True)


def _classifier_record(query_analysis: dict[str, Any]) -> dict[str, Any]:
    """Record deterministic intent analysis as classification, not ML inference."""
    return {
        "available": True,
        "type": "deterministic_query_intent",
        "is_ml_classifier": False,
        "intent": query_analysis["intent"],
    }


def _llm_configuration_lines(provider: str, model: str) -> list[str]:
    """Format report details from the active generation client's configuration."""
    return [f"- LLM provider: `{provider}`; model: `{model}`; temperature 0.1."]


def _reusable_checkpoint_records(
    checkpoint: dict[str, Any],
    dataset: str,
    morphology_enabled: bool,
    provider: str,
    model: str,
) -> dict[str, dict[str, Any]]:
    """Return only successful records with matching dataset and runtime metadata."""
    if not isinstance(checkpoint, dict) or any((
        checkpoint.get("dataset") != dataset,
        checkpoint.get("morphology_enabled") is not morphology_enabled,
        checkpoint.get("llm_provider") != provider,
        checkpoint.get("llm_model") != model,
    )):
        return {}
    return {
        record["id"]: record
        for record in checkpoint.get("items", [])
        if isinstance(record, dict)
        and record.get("id")
        and record.get("dataset") == dataset
        and record.get("morphology_enabled") is morphology_enabled
        and record.get("llm_provider") == provider
        and record.get("llm_model") == model
        and record.get("generated_answer") is not None
        and not record.get("generation_error")
    }


def _query_type(item: dict[str, Any]) -> str:
    if item.get("should_abstain"):
        return "abstention"
    if item.get("category") == "comparisons":
        return "comparison"
    if item.get("intent") == "explicit_provision":
        return "explicit_provision"
    return "normal"


def _citation_jurisdictions(
    citation_validation: dict[str, Any], chunks: list[dict[str, Any]]
) -> list[str]:
    by_id = {str(chunk.get("chunk_id")): str(chunk.get("jurisdiction") or "unknown") for chunk in chunks}
    found: set[str] = set()
    for citation in citation_validation.get("citations", []):
        for chunk_id in citation.get("matched_chunk_ids", []):
            if str(chunk_id) in by_id:
                found.add(by_id[str(chunk_id)])
    return sorted(found)


def _process_item(
    item: dict[str, Any], ranked: list[dict[str, Any]], llm: OllamaClient,
    context_top_k: int, started: float,
) -> dict[str, Any]:
    question = item["query"]
    query_analysis = analyze_legal_query(question)
    # Retrieve enough candidates to reproduce Recall@10; use the app's configured top-k
    # prefix as the actual production prompt context.
    evidence = ranked[:context_top_k]
    retrieval_rows = []
    for rank, chunk in enumerate(ranked, 1):
        retrieval_rows.append({
            "rank": rank,
            "chunk_id": chunk.get("chunk_id"),
            "document_id": chunk.get("document_id"),
            "document_name": chunk.get("document_name"),
            "filename": chunk.get("filename"),
            "jurisdiction": chunk.get("jurisdiction"),
            "provision_type": chunk.get("provision_type"),
            "provision_number": chunk.get("provision_number"),
            "provision_title": chunk.get("provision_title"),
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "dense_rank": chunk.get("dense_rank"),
            "bm25_rank": chunk.get("bm25_rank"),
            "hybrid_score": chunk.get("hybrid_score"),
            "text": chunk.get("text", ""),
            "used_in_prompt": rank <= context_top_k,
        })
    generation_error = None
    generated_answer: str | None = None
    validation: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    confidence: dict[str, Any] | None = None
    final_result: dict[str, Any] | None = None
    failure_stage: str | None = None
    try:
        generated_answer = _generate_grounded_answer(question, evidence, llm)
        validation = validate_citations(generated_answer, evidence)
        verification = verify_claims(generated_answer, evidence)
        confidence = score_confidence(question, evidence, validation)
        displayed_answer = apply_confidence_decision(generated_answer, confidence)
        final_result = build_rag_result(
            question, displayed_answer, evidence, validation, confidence, generated_answer
        )
    except Exception as error:
        generation_error = f"{type(error).__name__}: {error}"
        failure_stage = "answer_generation_or_downstream_validation"
    elapsed = round(time.perf_counter() - started, 3)
    target_ranks = []
    for target in item["expected_targets"]:
        rank = next((position for position, row in enumerate(ranked, 1) if matches_target(row, target)), None)
        target_ranks.append({"target": target, "rank_top_10": rank})
    actual_decision = confidence.get("decision") if confidence else (
        "generation_error" if generation_error else None
    )
    citation_jurisdictions = _citation_jurisdictions(validation or {}, evidence)
    expected_jurisdictions = sorted({
        target.get("jurisdiction") for target in item["expected_targets"] if target.get("jurisdiction")
    }) or ([item["jurisdiction"]] if item["jurisdiction"] != "all" else [])
    return {
        "id": item["id"],
        "question": question,
        "expected_category": item["category"],
        "expected_jurisdiction": item["jurisdiction"],
        "expected_evidence_jurisdictions": expected_jurisdictions,
        "query_type": _query_type(item),
        "query_analysis": {
            "intent": query_analysis["intent"],
            "explicit_provision": query_analysis["explicit_provision"],
            "jurisdictions_requested": query_analysis["jurisdictions_requested"],
        },
        "classifier": _classifier_record(query_analysis),
        "llm_provider": llm.provider,
        "llm_model": llm.model,
        "dataset": str(EVAL_PATH.relative_to(PROJECT_ROOT)),
        "morphology_enabled": False,
        "expected_targets": item["expected_targets"],
        "target_ranks_top_10": target_ranks,
        "retrieved_chunks": retrieval_rows,
        "prompt_context_top_k": context_top_k,
        "retrieved_jurisdictions": sorted({str(row.get("jurisdiction") or "unknown") for row in evidence}),
        "generated_answer": generated_answer,
        "final_answer": final_result.get("answer") if final_result else None,
        "citations_extracted": (validation or {}).get("citations", []),
        "citation_validation": validation,
        "cited_jurisdictions": citation_jurisdictions,
        "claim_verification": verification,
        "confidence": confidence,
        "decision": actual_decision,
        "actual_abstained": confidence.get("decision") == "abstain" if confidence else None,
        "expected_abstention": bool(item["should_abstain"]),
        "reason_for_abstention": confidence.get("reasons", []) if confidence and confidence.get("decision") == "abstain" else [],
        "generation_error": generation_error,
        "failure_stage": failure_stage,
        "latency_seconds": elapsed,
        "manual_review": "PENDING",
    }


def _citation_and_claim_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    answered = [record for record in records if record["generated_answer"] is not None]
    citation_count = valid_count = supported_citations = invalid_count = citation_answers = 0
    missing_expected = 0
    claim_total = claim_supported = claim_uncertain = claim_unsupported = claim_covered = 0
    for record in answered:
        validation = record.get("citation_validation") or {}
        citations = validation.get("citations", [])
        total = len(citations)
        valid = sum(bool(citation.get("valid")) for citation in citations)
        supported = sum(bool(citation.get("matched_chunk_ids")) for citation in citations)
        citation_count += total
        valid_count += valid
        supported_citations += supported
        invalid_count += total - valid
        citation_answers += total > 0
        claims = record.get("claim_verification") or {}
        claim_total += claims.get("claim_count", 0)
        claim_supported += claims.get("supported_claims", 0)
        claim_uncertain += claims.get("uncertain_claims", 0)
        claim_unsupported += claims.get("unsupported_claims", 0)
        claim_covered += sum(bool(c.get("citation_valid") and c.get("evidence_found")) for c in claims.get("claims", []))
        missing_expected += sum(not claim.get("citations") for claim in claims.get("claims", []))
    return {
        "evaluated_answers": len(answered),
        "answers_with_citations": citation_answers,
        "citation_presence_rate": citation_answers / len(answered) if answered else 0.0,
        "total_citations": citation_count,
        "valid_citations": valid_count,
        "citation_validity_rate": valid_count / citation_count if citation_count else 0.0,
        "retrieval_supported_citations": supported_citations,
        "citation_retrieval_support_rate": supported_citations / citation_count if citation_count else 0.0,
        "invalid_citation_count": invalid_count,
        "missing_citations_where_expected": missing_expected,
        "total_claims": claim_total,
        "supported_claims": claim_supported,
        "uncertain_claims": claim_uncertain,
        "unsupported_claims": claim_unsupported,
        "claim_citation_coverage": claim_covered / claim_total if claim_total else 0.0,
    }


def _abstention_metrics(items: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {record["id"]: record for record in records}
    expected = [item for item in items if item["should_abstain"]]
    answerable = [item for item in items if not item["should_abstain"]]
    def is_generation_error(record: dict[str, Any] | None) -> bool:
        return bool(record and (
            record.get("decision") == "generation_error" or record.get("generation_error")
        ))

    successful = [record for record in records if not is_generation_error(record)
                  and record.get("generated_answer") is not None]
    evaluated = [record for record in successful if isinstance(record.get("actual_abstained"), bool)]
    generation_errors = [record for record in records if is_generation_error(record)]
    evaluated_expected = [
        item for item in expected
        if item["id"] in by_id
        and not is_generation_error(by_id[item["id"]])
        and by_id[item["id"]].get("generated_answer") is not None
        and isinstance(by_id[item["id"]].get("actual_abstained"), bool)
    ]
    unevaluated_expected = [item for item in expected if item not in evaluated_expected]
    actual = [record for record in evaluated if record.get("actual_abstained") is True]
    correct = sum(by_id[item["id"]].get("actual_abstained") is True for item in evaluated_expected)
    incorrect = [item["id"] for item in evaluated_expected
                 if by_id[item["id"]].get("actual_abstained") is False]
    false_abstentions = [item["id"] for item in answerable if item["id"] in by_id
                         and not is_generation_error(by_id[item["id"]])
                         and by_id[item["id"]].get("actual_abstained") is True]
    return {
        "total_queries": len(items),
        "successful_generation_queries": len(successful),
        "generation_error_queries": len(generation_errors),
        "generation_error_ids": [record["id"] for record in generation_errors],
        "expected_abstention_cases": len(expected),
        "expected_abstention_ids": [item["id"] for item in expected],
        "evaluated_expected_abstention_cases": len(evaluated_expected),
        "unevaluated_expected_abstention_cases": len(unevaluated_expected),
        "unevaluated_expected_abstention_ids": [item["id"] for item in unevaluated_expected],
        "evaluated_queries": len(evaluated),
        "correct_abstentions": correct,
        "incorrect_answers_on_abstention_cases": len(incorrect),
        "incorrect_answer_ids": incorrect,
        "false_abstentions_on_answerable_queries": len(false_abstentions),
        "false_abstention_ids": false_abstentions,
        "actual_abstentions": len(actual),
        "abstention_rate": len(actual) / len(evaluated) if evaluated else 0.0,
    }


def _jurisdiction_metrics(items: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {record["id"]: record for record in records}
    india_only_international = []
    international_only_india = []
    comparisons = []
    for item in items:
        record = by_id[item["id"]]
        cited = set(record.get("cited_jurisdictions", []))
        retrieved = set(record.get("retrieved_jurisdictions", []))
        if item["jurisdiction"] == "India" and record.get("decision") not in {"abstain", "generation_error"} and cited == {"International"}:
            india_only_international.append(item["id"])
        if item["jurisdiction"] == "International" and record.get("decision") not in {"abstain", "generation_error"} and cited == {"India"}:
            international_only_india.append(item["id"])
        if item["category"] == "comparisons":
            comparisons.append({
                "id": item["id"], "retrieved_jurisdictions": sorted(retrieved),
                "cited_jurisdictions": sorted(cited),
                "retrieves_both": {"India", "International"}.issubset(retrieved),
                "cites_both": {"India", "International"}.issubset(cited),
                "decision": record.get("decision"),
            })
    violations = []
    for item in items:
        if item["jurisdiction"] not in {"India", "International"}:
            continue
        for record in [by_id[item["id"]]]:
            violations.extend(
                {"id": item["id"], "rank": row["rank"], "expected": item["jurisdiction"], "actual": row["jurisdiction"]}
                for row in record["retrieved_chunks"][:record["prompt_context_top_k"]]
                if row["jurisdiction"] != item["jurisdiction"]
            )
    return {
        "retrieval_jurisdiction_violations": violations,
        "india_answers_using_only_international_citations": india_only_international,
        "international_answers_using_only_india_citations": international_only_india,
        "comparison_queries": comparisons,
        "answer_text_jurisdiction_correctness": "requires manual review; not inferred from mention matching",
    }


def _regression_checks() -> dict[str, Any]:
    env = os.environ.copy()
    env["MORPHOLOGY_EXPANSION_ENABLED"] = "false"
    commands = {
        "unit_tests": [sys.executable, "-B", "-m", "unittest", "discover", "-s", "rag-service/tests", "-p", "test_*.py"],
        "stage_5a_1": [sys.executable, "-B", "rag-service/tests/evaluate_retrieval.py"],
        "42_query_retrieval": [sys.executable, "-B", "rag-service/tests/evaluate_full_retrieval.py"],
        "stage_6k_holdout": [sys.executable, "-B", "rag-service/tests/evaluate_holdout_generalization.py"],
    }
    outcomes: dict[str, Any] = {}
    for name, command in commands.items():
        print(f"Running regression: {name}", flush=True)
        try:
            result = subprocess.run(command, cwd=PROJECT_ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
            output = result.stdout
            selected_lines = [line.strip() for line in output.splitlines() if any(
                label in line for label in ("Ran ", "OK", "Recall@", "RECALL@", "MRR:",
                                            "Violations:", "Deterministic:", "Ranking mismatches",
                                            "Stage 6K status:", "Regression checks:"))]
            outcomes[name] = {"passed": result.returncode == 0, "returncode": result.returncode,
                              "summary": selected_lines}
        except subprocess.TimeoutExpired:
            outcomes[name] = {"passed": False, "returncode": None, "summary": ["Timed out after 900 seconds."]}
    return outcomes


def _report_text(
    items: list[dict[str, Any]],
    records: list[dict[str, Any]],
    retrieval_metrics: dict[str, Any],
    retrieval_preflight: dict[str, Any],
    citation_claims: dict[str, Any],
    abstentions: dict[str, Any],
    jurisdictions: dict[str, Any],
    regressions: dict[str, Any],
    app_top_k: int,
    llm_provider: str,
    llm_model: str,
) -> tuple[str, str]:
    generated = [record for record in records if record.get("generated_answer") is not None]
    abstain_by_id = {record["id"]: record for record in records}
    failures = []
    for item, record in zip(items, records):
        reasons = []
        citation_validation = record.get("citation_validation") or {}
        claim_verification = record.get("claim_verification") or {}
        if record.get("generation_error"):
            reasons.append("generation/pipeline error")
        if citation_validation.get("invalid_citations", 0):
            reasons.append("invalid citation")
        if claim_verification.get("unsupported_claims", 0):
            reasons.append("claim without valid evidence citation (not semantic entailment)")
        if item["should_abstain"] and record.get("actual_abstained") is False:
            reasons.append("answered an expected-abstention case")
        if not item["should_abstain"] and record.get("actual_abstained") is True:
            reasons.append("false abstention")
        if claim_verification.get("claim_count", 0) and not record.get("citations_extracted"):
            reasons.append("claim text with no citation")
        if item.get("expected_targets") and not any(r.get("rank_top_10") for r in record["target_ranks_top_10"]):
            reasons.append("no expected target in retrieval Top 10")
        if reasons:
            failures.append({"id": item["id"], "reasons": reasons})

    issue_count = (citation_claims["invalid_citation_count"]
                   + citation_claims["missing_citations_where_expected"]
                   + abstentions["incorrect_answers_on_abstention_cases"]
                   + abstentions["false_abstentions_on_answerable_queries"]
                   + sum(bool(record.get("generation_error")) for record in records)
                   + len(jurisdictions["retrieval_jurisdiction_violations"]))
    regression_failure = any(not result["passed"] for result in regressions.values())
    if len(generated) == 0:
        status = "FAIL"
        observation = "The evaluator reached no successful answer generations; answer-quality metrics are unavailable."
    elif issue_count or regression_failure:
        status = "WARN"
        observation = "The automated run completed, but answer/citation/abstention issues or regression failures require review. Automated scores do not establish legal correctness."
    else:
        status = "PASS"
        observation = "The evaluator completed, reproduced retrieval metrics, and passed regression checks. Human review is still required to assess legal correctness."

    lines = [
        "# Stage 6L End-to-End Answer Quality Evaluation", "",
        "## AUTOMATED METRICS", "",
        "### Evaluation configuration", "",
        "- Pipeline components: existing `LegalRetriever`, query analyzer, prompt builder and citation labeling through the app answer helper, citation validator, confidence scorer, and claim verifier.",
        "- Query classification: deterministic query-intent analysis (not an ML classifier); the detected intent is recorded for every query.",
        *_llm_configuration_lines(llm_provider, llm_model),
        "- `MORPHOLOGY_EXPANSION_ENABLED=false`; unchanged Stage 6D retrieval configuration.",
        f"- Retrieval metrics: standard Top-10 evaluation; answer prompts used application `top_k={app_top_k}`.",
        "- Each query was generated once. Latency covers retrieval, generation, citation validation, claim verification, confidence scoring, and result assembly.", "",
        "### Dataset composition", "",
        f"- Items: {len(items)}; answerable: {sum(not item['should_abstain'] for item in items)}; expected abstention/out-of-scope: {sum(bool(item['should_abstain']) for item in items)}.",
        f"- Categories: {dict(Counter(item['category'] for item in items))}.",
        f"- Intents: {dict(Counter(item['intent'] for item in items))}.",
        f"- Jurisdictions: {dict(Counter(item['jurisdiction'] for item in items))}.", "",
        "### Retrieval metrics", "",
        f"Preflight Stage 6D metric match: **{'PASS' if retrieval_preflight['matches_baseline'] else 'FAIL'}**.",
        "| Metric | Accepted Stage 6D | Reproduced |", "|---|---:|---:|",
    ]
    for key, expected in STAGE_6D_BASELINE.items():
        lines.append(f"| {key} | {expected:.4f} | {retrieval_metrics[key]:.4f} |")
    lines += ["", "### Citation metrics", "",
              f"- Answers containing citations: {citation_claims['answers_with_citations']}/{citation_claims['evaluated_answers']} ({citation_claims['citation_presence_rate']:.1%}).",
              f"- Citation validity: {citation_claims['valid_citations']}/{citation_claims['total_citations']} ({citation_claims['citation_validity_rate']:.1%}).",
              f"- Citation retrieval support: {citation_claims['retrieval_supported_citations']}/{citation_claims['total_citations']} ({citation_claims['citation_retrieval_support_rate']:.1%}).",
              f"- Invalid citations: {citation_claims['invalid_citation_count']}.",
              f"- Claims with no citation where one is expected: {citation_claims['missing_citations_where_expected']}.",
              "- Validity uses the existing metadata validator; retrieval support counts citations with matched retrieved chunk IDs. These are integrity checks, not relevance or entailment judgments.", "",
              "### Claim-level metrics", "",
              f"- Total claims: {citation_claims['total_claims']}.",
              f"- Supported: {citation_claims['supported_claims']}/{citation_claims['total_claims']}.",
              f"- Uncertain: {citation_claims['uncertain_claims']}/{citation_claims['total_claims']}.",
              f"- Unsupported: {citation_claims['unsupported_claims']}/{citation_claims['total_claims']}.",
              f"- Existing claim citation/evidence coverage: {citation_claims['claim_citation_coverage']:.1%}.",
              "- The existing verifier does not establish semantic entailment; citation-matched claims remain `uncertain`, not supported.", "",
              "### Abstention metrics", "",
              f"- Total queries: {abstentions['total_queries']}; successful generations: {abstentions['successful_generation_queries']}; generation errors: {abstentions['generation_error_queries']} ({', '.join(abstentions['generation_error_ids']) or 'none'}).",
              f"- Correct abstentions on expected-abstention cases: {abstentions['correct_abstentions']}/{abstentions['expected_abstention_cases']}.",
              f"- Expected abstention IDs: {', '.join(abstentions['expected_abstention_ids']) or 'none'}.",
              f"- Expected abstention cases evaluated: {abstentions['evaluated_expected_abstention_cases']}; unevaluated after generation errors or missing decisions: {abstentions['unevaluated_expected_abstention_cases']} ({', '.join(abstentions['unevaluated_expected_abstention_ids']) or 'none'}).",
              f"- Incorrect answers on expected-abstention cases: {abstentions['incorrect_answers_on_abstention_cases']} ({', '.join(abstentions['incorrect_answer_ids']) or 'none'}).",
              f"- False abstentions on answerable queries: {abstentions['false_abstentions_on_answerable_queries']} ({', '.join(abstentions['false_abstention_ids']) or 'none'}).",
              f"- Actual confidence abstentions: {abstentions['actual_abstentions']}; rate among evaluated queries: {abstentions['abstention_rate']:.1%} ({abstentions['evaluated_queries']} evaluated).",
              "- A generation-error query is unevaluated for abstention and is excluded from correct/incorrect abstention counts. An actual abstention means the existing confidence decision was `abstain`; model text alone was not treated as the pipeline decision.", "",
              "### Jurisdiction metrics", "",
              f"- Retrieved-evidence jurisdiction violations on jurisdiction-filtered queries: {len(jurisdictions['retrieval_jurisdiction_violations'])}.",
              f"- India queries answered with citations from only International evidence: {len(jurisdictions['india_answers_using_only_international_citations'])}.",
              f"- International queries answered with citations from only India evidence: {len(jurisdictions['international_answers_using_only_india_citations'])}.",
              "- Answer-text jurisdiction correctness: manual review required; not inferred from jurisdiction-name mentions.",
              "- Comparison behavior by query:"]
    for comparison in jurisdictions["comparison_queries"]:
        lines.append(f"  - {comparison['id']}: retrieved {comparison['retrieved_jurisdictions']}; cited {comparison['cited_jurisdictions']}; both retrieved={comparison['retrieves_both']}; both cited={comparison['cites_both']}; decision={comparison['decision']}.")
    lines += ["", "### Failure examples", ""]
    if failures:
        for failure in failures[:15]:
            lines.append(f"- {failure['id']}: {', '.join(failure['reasons'])}.")
    else:
        lines.append("- No automated failure signals were detected; this does not mean the answers are legally correct.")
    lines += ["", "### Per-query results", "",
              "Answers are reproduced exactly as returned by the existing app answer helper, including source citations it appends when the model omits them. `manual_review` remains `PENDING` for every item.", ""]
    for record in records:
        lines += [f"#### {record['id']} — {record['question']}", "",
                  f"- Expected category/jurisdiction/type: {record['expected_category']} / {record['expected_jurisdiction']} / {record['query_type']}.",
                  f"- Expected targets/ranks (Top 10): {json.dumps(record['target_ranks_top_10'], ensure_ascii=False)}.",
                  f"- Retrieved/cited jurisdictions: {record['retrieved_jurisdictions']} / {record['cited_jurisdictions']}.",
                  f"- Confidence/decision/actual abstention: {json.dumps(record['confidence'], ensure_ascii=False)} / {record['decision']} / {record['actual_abstained']}.",
                  f"- Citation validation: {json.dumps(record['citation_validation'], ensure_ascii=False)}.",
                  f"- Claim verification summary: {json.dumps({k: (record.get('claim_verification') or {}).get(k) for k in ('claim_count','supported_claims','uncertain_claims','unsupported_claims','citation_coverage','overall_status')}, ensure_ascii=False)}.",
                  f"- Latency: {record['latency_seconds']:.3f}s; manual review: PENDING.",
                  "- Retrieved evidence (rank, document, provision, jurisdiction, pages, component ranks):"]
        for chunk in record["retrieved_chunks"][:record["prompt_context_top_k"]]:
            lines.append(f"  - {chunk['rank']}. {chunk['document_name']} {chunk['provision_type']} {chunk['provision_number']} ({chunk['jurisdiction']}), pp. {chunk['page_start']}-{chunk['page_end']}; dense={chunk['dense_rank']}, BM25={chunk['bm25_rank']}.")
        lines += ["- Generated answer:", "", record.get("generated_answer") or "[No answer generated.]", "",
                  f"- Final displayed result: {record.get('final_answer') or '[No final result assembled.]'}", ""]

    lines += ["## MANUAL REVIEW REQUIRED", "",
              f"Use [end_to_end_review_template.md]({TEMPLATE_PATH.name}) for each answer. Automated labels are not assigned. Reviewers must assess relevance, legal reasoning, provision references, jurisdiction, caution, abstention, and overall quality.", "",
              "### Limitations", "",
              "- Query classification uses deterministic query-intent analysis; it is not an ML classifier.",
              "- Citation validity checks metadata against retrieved chunks; it does not prove that a cited provision is relevant or supports the nearby claim.",
              "- The claim verifier reports citation/evidence coverage and deliberately does not determine semantic support.",
              "- Confidence is a deterministic retrieval/citation sufficiency signal, not a probability of legal correctness.",
              "- Abstention metrics evaluate the existing confidence decision and do not establish whether the model’s legal reasoning was correct.",
              "- Jurisdiction behavior inferred from cited sources does not replace checking the answer’s legal interpretation.",
              "- LLM outputs are single-run samples; this evaluation does not establish answer determinism or legal correctness.",
              "- This is a research evaluation, not legal advice; no automated metric guarantees legal correctness.", "",
              "### Final observations", "",
              "The retrieval preflight was required to match the accepted Stage 6D metrics before answer generation. Citation and claim metrics should be read as source-integrity and citation-coverage evidence only. Manual review is required before drawing conclusions about legal accuracy.", "",
              "### Regression checks run after evaluation", ""]
    for name, result in retrieval_preflight.get("regressions", {}).items():
        lines.append(f"- {name}: {'PASS' if result['passed'] else 'FAIL'}.")
        lines.extend(f"  - {line}" for line in result.get("summary", []))
    if retrieval_preflight.get("regressions") is None:
        lines.append("- Regression checks were not run.")
    lines += ["", f"STAGE 6L STATUS: {status}", ""]
    return "\n".join(lines), status


def main() -> None:
    _load_project_env()
    old_flag = os.environ.get("MORPHOLOGY_EXPANSION_ENABLED")
    os.environ["MORPHOLOGY_EXPANSION_ENABLED"] = "false"
    items = load_items()
    # Fail closed before any LLM call if the accepted retrieval baseline moved.
    with open(os.devnull, "w", encoding="utf-8") as sink:
        with contextlib.redirect_stdout(sink):
            preflight = evaluate_retrieval()
    measured = preflight["overall"]
    mismatch = {key: {"expected": expected, "actual": measured.get(key)}
                for key, expected in STAGE_6D_BASELINE.items() if measured.get(key) != expected}
    if mismatch:
        if old_flag is None:
            os.environ.pop("MORPHOLOGY_EXPANSION_ENABLED", None)
        else:
            os.environ["MORPHOLOGY_EXPANSION_ENABLED"] = old_flag
        raise RuntimeError(f"Stage 6D retrieval preflight did not reproduce; stopped before LLM calls: {mismatch}")

    retriever = LegalRetriever()
    llm = OllamaClient()
    dataset_identity = str(EVAL_PATH.relative_to(PROJECT_ROOT))
    app_top_k = get_top_k()
    retrieval_top_k = max(10, app_top_k)
    retrieval_results: dict[str, list[dict[str, Any]]] = {}
    records_by_id: dict[str, dict[str, Any]] = {}
    if DATA_PATH.is_file():
        try:
            checkpoint = json.loads(DATA_PATH.read_text(encoding="utf-8-sig"))
            records_by_id = _reusable_checkpoint_records(
                checkpoint, dataset_identity, False, llm.provider, llm.model
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            records_by_id = {}
    print(f"Stage 6D retrieval baseline reproduced: {measured}", flush=True)
    print(f"Running {len(items)} end-to-end queries with provider {llm.provider}, model {llm.model}; prompt context top-k={app_top_k}.", flush=True)
    if records_by_id:
        print(f"Resuming from {len(records_by_id)} saved query results.", flush=True)
    for index, item in enumerate(items, 1):
        jurisdiction = item["jurisdiction"] if item["jurisdiction"] in {"India", "International"} else "all"
        saved = records_by_id.get(item["id"])
        if saved:
            retrieval_results[item["id"]] = saved["retrieved_chunks"]
            print(f"[{index}/{len(items)}] {item['id']}: resumed saved answer", flush=True)
            continue
        # Retain Top-10 results for retrieval metrics while the app uses its configured prefix.
        started = time.perf_counter()
        retrieval_results[item["id"]] = retriever.retrieve(
            item["query"], top_k=retrieval_top_k, jurisdiction=jurisdiction
        )
        record = _process_item(item, retrieval_results[item["id"]], llm, app_top_k, started)
        records_by_id[item["id"]] = record
        checkpoint_records = [records_by_id[item_row["id"]] for item_row in items if item_row["id"] in records_by_id]
        DATA_PATH.write_text(json.dumps({
            "dataset": dataset_identity,
            "morphology_enabled": False,
            "llm_provider": llm.provider,
            "llm_model": llm.model,
            "checkpoint": True,
            "completed_queries": len(checkpoint_records),
            "items": checkpoint_records,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outcome = "ERROR" if record["generation_error"] else str(record["decision"])
        print(f"[{index}/{len(items)}] {item['id']}: {outcome} ({record['latency_seconds']:.1f}s)", flush=True)

    records = [records_by_id[item["id"]] for item in items]

    if old_flag is None:
        os.environ.pop("MORPHOLOGY_EXPANSION_ENABLED", None)
    else:
        os.environ["MORPHOLOGY_EXPANSION_ENABLED"] = old_flag
    answerable = [item for item in items if not item["should_abstain"]]
    retrieval_rankings = {item["id"]: _target_rankings(retrieval_results[item["id"]], item["expected_targets"])
                          for item in answerable}
    retrieval_metrics = _metric_record(answerable, retrieval_rankings)
    if any(retrieval_metrics.get(key) != measured.get(key) for key in STAGE_6D_BASELINE):
        raise RuntimeError(f"Per-query retrieval metrics {retrieval_metrics} differ from preflight {measured}; do not trust answer evaluation.")

    # Run existing regression checks after the requested end-to-end evaluation.
    print("End-to-end generation completed; running regression suite and retrieval evaluations.", flush=True)
    regressions = _regression_checks()
    citation_claims = _citation_and_claim_metrics(records)
    abstentions = _abstention_metrics(items, records)
    jurisdictions = _jurisdiction_metrics(items, records)
    preflight_details = {
        "matches_baseline": not mismatch,
        "regressions": regressions,
    }
    for record in records:
        record["evaluation_retrieval_top_k"] = retrieval_top_k
    report, status = _report_text(
        items, records, retrieval_metrics, preflight_details, citation_claims,
        abstentions, jurisdictions, regressions, app_top_k, llm.provider, llm.model,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    DATA_PATH.write_text(json.dumps({
        "dataset": dataset_identity,
        "morphology_enabled": False,
        "llm_provider": llm.provider,
        "llm_model": llm.model,
        "stage_6d_baseline": retrieval_metrics,
        "citation_claim_metrics": citation_claims,
        "abstention_metrics": abstentions,
        "jurisdiction_metrics": jurisdictions,
        "regression_checks": regressions,
        "items": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Stage 6L status: {status}")
    print(f"Report: {REPORT_PATH}")
    print(f"Structured per-query data: {DATA_PATH}")
    print("Retrieval metrics:", json.dumps(retrieval_metrics, sort_keys=True))
    print("Citation/claim metrics:", json.dumps(citation_claims, sort_keys=True))
    print("Abstention metrics:", json.dumps(abstentions, sort_keys=True))
    print("Regression checks:", json.dumps({key: value["passed"] for key, value in regressions.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
