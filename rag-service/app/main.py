"""Interactive command-line legal RAG application."""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

from app.llm_client import IncompleteGenerationError, OllamaClient, current_request_id
from app.answer_postprocessor import postprocess_generated_answer
from app.prompt_builder import build_prompt, format_source_citation, insert_citation_labels
from app.retriever import LegalRetriever, explicit_provision_diagnostic, get_top_k
from app.abstention_guard import evaluate_abstention_guard

DISCLAIMER = "This information is provided for research/educational purposes and is not legal advice."
logger = logging.getLogger(__name__)


def _log_stage_duration(stage: str, started_at: float) -> None:
    logger.warning(
        "RAG_STAGE_TIMING request_id=%s stage=%s elapsed_ms=%.3f",
        current_request_id(),
        stage,
        (time.perf_counter() - started_at) * 1000,
    )


def _source_record(chunk: dict[str, Any]) -> dict[str, Any]:
    """Return the requested structured source data for the final response."""
    fields = (
        "chunk_id", "document_name", "filename", "jurisdiction", "provision_type",
        "provision_number", "provision_title", "chapter_or_part", "subsection_path",
        "page_start", "page_end", "source_pages", "extraction_methods", "content_type",
        "hybrid_score", "dense_rank", "bm25_rank", "query_intent", "intent_bonus", "final_score",
    )
    source = {field: chunk.get(field) for field in fields}
    source["citation"] = format_source_citation(chunk)
    return source


def _print_retrieved_context(chunks: list[dict[str, Any]]) -> None:
    """Display hybrid scores and component ranks for debugging."""
    print("\nHYBRID RETRIEVAL")
    if not chunks:
        print("No legal chunks were retrieved.")
        return
    for rank, chunk in enumerate(chunks, start=1):
        provision_type = chunk.get("provision_type") or chunk.get("content_type") or "general"
        provision_number = chunk.get("provision_number")
        provision = f"{provision_type} {provision_number}" if provision_number else provision_type
        print(
            f"{rank}. {chunk.get('document_name') or chunk.get('filename')} | {provision} | "
            f"pages {chunk.get('page_start')}-{chunk.get('page_end')} | "
            f"final_score={chunk.get('final_score'):.6f} (RRF={chunk.get('hybrid_score'):.6f}, "
            f"intent_bonus={chunk.get('intent_bonus'):.6f}) | intent={chunk.get('query_intent')} | "
            f"dense_rank={chunk.get('dense_rank')} | bm25_rank={chunk.get('bm25_rank')}"
        )


def _print_citation_validation(validation: dict[str, Any]) -> None:
    """Display citation integrity results without changing the generated answer."""
    status = "VALID" if validation["valid"] else "INVALID"
    print("\nCITATION VALIDATION\n")
    print(f"Status: {status}")
    print(f"Citations: {validation['total_citations']}")
    print(f"Valid: {validation['valid_citations']}")
    print(f"Invalid: {validation['invalid_citations']}")
    print(f"Coverage: {validation['citation_coverage']:.0%}")
    if not validation["citations"]:
        print("No citations found in the answer.")
        return
    for index, citation in enumerate(validation["citations"], start=1):
        print(f"\n{index}. {citation['raw']}")
        print("   VALID" if citation["valid"] else "   INVALID")
        for reason in citation["errors"]:
            print(f"   Reason: {reason}")

def _generate_grounded_answer(
    question: str, chunks: list[dict[str, Any]], llm: OllamaClient,
    diagnostics: dict[str, Any] | None = None,
) -> str:
    """Generate with source markers, then render citations from retrieved metadata."""
    if not chunks:
        return "The available retrieved legal sources do not provide enough information to answer this question."
    prompt_started = time.perf_counter()
    try:
        messages, citation_map = build_prompt(question, chunks)
        if diagnostics is not None:
            diagnostics["prompt_source_references"] = [
                {"source_id": source_id, "citation": citation}
                for source_id, citation in citation_map.items()
            ]
    finally:
        _log_stage_duration("prompt_construction", prompt_started)
    generation_started = time.perf_counter()
    try:
        generated_text = llm.generate(messages)
        if diagnostics is not None:
            diagnostics["raw_llm_response"] = generated_text
    except IncompleteGenerationError as error:
        if diagnostics is not None:
            diagnostics["raw_partial_llm_response"] = error.partial_text
        error.partial_answer = insert_citation_labels(error.partial_text, citation_map).rstrip()
        raise
    finally:
        _log_stage_duration("llm_generate", generation_started)
    answer = insert_citation_labels(generated_text, citation_map).rstrip()
    return answer


def build_rag_result(
    question: str,
    answer: str,
    chunks: list[dict[str, Any]],
    citation_validation: dict[str, Any] | None = None,
    confidence: dict[str, Any] | None = None,
    generated_answer: str | None = None,
) -> dict[str, Any]:
    """Assemble the pipeline output as a question, answer, and cited source records."""
    return {
        "question": question,
        "answer": f"{answer.rstrip()}\n\n{DISCLAIMER}",
        "generated_answer": generated_answer if generated_answer is not None else answer,
        "confidence": confidence,
        "sources": [_source_record(chunk) for chunk in chunks],
        "citation_validation": citation_validation,

    }


def _print_confidence(confidence: dict[str, Any]) -> None:
    """Display the deterministic sufficiency score and its contributing reasons."""
    print("\nCONFIDENCE\n")
    print(f"Score: {confidence['score']:.2f}")
    print(f"Level: {confidence['level']}")
    print(f"Decision: {confidence['decision']}")
    print("Reasons:")
    for reason in confidence["reasons"]:
        print(f"- {reason}")

def _print_claim_verification(result: dict[str, Any]) -> None:
    """Display concise citation coverage without implying semantic verification."""
    covered = sum(1 for claim in result["claims"] if claim["citation_valid"] and claim["evidence_found"])
    print("\nCLAIM VERIFICATION")
    print(f"Claims detected: {result['claim_count']}")
    print(f"Claims with valid evidence citations: {covered}")
    print(f"Claims without valid evidence citations: {result['claim_count'] - covered}")
    print(f"Citation/evidence coverage: {result['citation_coverage']:.2%}")
    print("Semantic claim support: NOT VERIFIED")
    if result.get("withheld_claim_count"):
        print(f"Generated claims withheld for missing citation matches: {result['withheld_claim_count']}")


def _print_retrieval_diagnostic(result: dict[str, Any] | None) -> None:
    """Show each requested provision's retrieval status without implying legal support."""
    if not result:
        return
    print("\nEXPLICIT PROVISION RETRIEVAL")
    for provision in result["requested"]:
        state = "FOUND" if provision["found"] else "MISSING"
        print(f"- {provision['type']} {provision['number']}: {state}")

def _handle_question(
    question: str, retriever: LegalRetriever, llm: OllamaClient, top_k: int
) -> None:
    """Retrieve, answer, validate citations, score sufficiency, and display the result."""
    chunks = retriever.retrieve(question, top_k)
    retrieval_diagnostic = explicit_provision_diagnostic(
        question, chunks, getattr(retriever, "chunks", None)
    )
    retrieval_debug = getattr(retriever, "last_retrieval_debug", None)
    if retrieval_debug:
        logging.getLogger(__name__).debug(
            "Retrieval query diagnostics: original=%r retrieval=%r morphology_applied=%s",
            retrieval_debug["original_query"], retrieval_debug["retrieval_query"],
            retrieval_debug["morphology_applied"],
        )
    _print_retrieved_context(chunks)
    _print_retrieval_diagnostic(retrieval_diagnostic)
    if retrieval_diagnostic and not retrieval_diagnostic["all_found"]:
        missing = ", ".join(
            f"{item['type']} {item['number']}" for item in retrieval_diagnostic["missing"]
        )
        message = (
            f"The retrieved evidence does not include the explicitly requested {missing}. "
            "I cannot complete the requested provision-by-provision explanation from the available sources."
        )
        result = build_rag_result(question, message, chunks)
        print("\nANSWER\n")
        print(result["answer"])
        return
    guard = evaluate_abstention_guard(question)
    if guard.should_abstain:
        result = build_rag_result(question, guard.explanation, chunks)
        print("\nANSWER\n")
        print(result["answer"])
        print(f"\nPRE-GENERATION ABSTENTION: {guard.category}")
        print(guard.explanation)
        print("\nSOURCES")
        print(json.dumps(result["sources"], ensure_ascii=False, indent=2))
        return

    try:
        generated_answer = _generate_grounded_answer(question, chunks, llm)
    except IncompleteGenerationError as error:
        print("\nINCOMPLETE RESPONSE: generation stopped before completion; do not rely on this as a complete answer.\n")
        print("The partial model output was withheld because it was not verified.")
        return
    processed = postprocess_generated_answer(question, generated_answer, chunks)
    result = build_rag_result(
        question, processed["answer"], chunks, processed["validation"],
        processed["confidence"], generated_answer
    )
    print("\nANSWER\n")
    print(result["answer"])
    for warning in processed["warnings"]:
        print(f"\nCAUTION: {warning}")
    _print_citation_validation(processed["validation"])
    _print_confidence(processed["confidence"])
    _print_claim_verification(processed["claim_verification"])
    print("\nSOURCES")
    print(json.dumps(result["sources"], ensure_ascii=False, indent=2))

def main() -> None:
    """Start the interactive command-line question loop."""
    try:
        top_k = get_top_k()
        retriever = LegalRetriever()
        llm = OllamaClient()
    except Exception as error:
        print(f"Unable to start legal RAG: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print("IP-SAKTI Sahayak legal RAG (type 'exit' or 'quit' to stop)")
    while True:
        try:
            question = input("\nQuestion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if question.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not question:
            continue
        try:
            _handle_question(question, retriever, llm, top_k)
        except Exception as error:
            print(f"\nRequest failed: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()




# Function	Main purpose
# _log_stage_duration()	Measures execution time.
# _source_record()	Prepares retrieved source information.
# _print_retrieved_context()	Displays retrieved chunks and scores.
# _print_citation_validation()	Displays citation validation results.
# _generate_grounded_answer()	Builds prompt and generates an LLM answer.
# build_rag_result()	Combines answer, confidence and sources.
# _print_confidence()	Displays confidence assessment.
# _print_claim_verification()	Displays claim/citation coverage.
# _print_retrieval_diagnostic()	Displays requested provision retrieval status.
# _handle_question()	Controls the processing of one question.
# main()	Starts the application and accepts questions.

# The most important thing to remember
# Your main.py acts like a manager.

# It doesn't perform every task itself. It calls the other files and makes sure they execute in the correct order.

# For example:
# - retriever.py finds relevant legal information.
# - prompt_builder.py prepares the LLM prompt.
# - llm_client.py communicates with Ollama.
# - answer_postprocessor.py processes the generated answer.
# - main.py coordinates all of them.





