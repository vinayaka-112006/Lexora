"""FastAPI contract for the existing IP-SAKTI Sahayak RAG pipeline."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.abstention_guard import evaluate_abstention_guard
from app.citation_validator import validate_citations
from app.claim_verifier import verify_claims
from app.confidence_scorer import apply_confidence_decision, score_confidence
from app.llm_client import (
    OllamaClient,
    current_request_id,
    groq_key_configuration_diagnostics,
    reset_current_request_id,
    set_current_request_id,
)
from app.main import _generate_grounded_answer, _source_record, build_rag_result
from app.retriever import LegalRetriever, get_top_k

logger = logging.getLogger(__name__)


def _log_stage_duration(stage: str, started_at: float) -> None:
    logger.warning(
        "RAG_STAGE_TIMING request_id=%s stage=%s elapsed_ms=%.3f",
        current_request_id(),
        stage,
        (time.perf_counter() - started_at) * 1000,
    )


def _safe_log_component(value: Any, *, pattern: str, fallback: str = "unknown") -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return fallback
    component = str(value)
    for key_name in ("GEMINI_API_KEY", "GROQ_API_KEY"):
        api_key = os.getenv(key_name)
        if api_key:
            component = component.replace(api_key, "[REDACTED]")
    component = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [REDACTED]", component)
    component = re.sub(
        r"(?i)(?:api[_-]?key|authorization|access[_-]?token)\s*[:=]\s*[^\s,;]+",
        "[REDACTED]",
        component,
    )
    if not re.fullmatch(pattern, component):
        return fallback
    return component[:100]


def _generation_failure_diagnostics(error: Exception, llm: Any | None) -> dict[str, Any]:
    provider = getattr(llm, "provider", None) or os.getenv("LLM_PROVIDER", "ollama")
    if provider not in {"gemini", "ollama", "groq"}:
        provider = "unknown"
    model = getattr(llm, "model", None)
    if not model:
        model_variable = {
            "gemini": "GEMINI_MODEL",
            "groq": "GROQ_MODEL",
            "ollama": "OLLAMA_MODEL",
        }.get(provider, "OLLAMA_MODEL")
        model = os.getenv(model_variable, "unknown")

    status = getattr(error, "provider_status", None)
    if status is None:
        status = getattr(error, "status_code", None)
    error_code = getattr(error, "provider_error_code", None)
    if error_code is None:
        error_code = getattr(error, "error_code", None)
    error_reason = getattr(error, "provider_error_reason", None)
    error_type = getattr(error, "provider_error_type", None)
    exception_class = getattr(error, "provider_exception_class", None) or type(error).__name__

    diagnostics: dict[str, Any] = {
        "provider": provider,
        "model": _safe_log_component(model, pattern=r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}"),
        "exception_class": _safe_log_component(
            exception_class, pattern=r"[A-Za-z_][A-Za-z0-9_.]{0,79}"
        ),
        "provider_status": _safe_log_component(status, pattern=r"[0-9]{3}"),
        "provider_error_code": _safe_log_component(
            error_code, pattern=r"[A-Za-z][A-Za-z0-9_.-]{0,79}"
        ),
        "provider_error_type": _safe_log_component(
            error_type, pattern=r"[A-Za-z][A-Za-z0-9_.-]{0,63}"
        ),
        "provider_error_reason": _safe_log_component(
            error_reason, pattern=r"[a-z_]{1,50}"
        ),
    }
    if provider == "groq":
        diagnostics.update(groq_key_configuration_diagnostics())
    return diagnostics

Decision = Literal["answer", "answer_with_caution", "abstain", "generation_error"]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    jurisdiction: str | None = None

    @field_validator("query")
    @classmethod
    def query_must_contain_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty or whitespace only")
        return value.strip()

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if value.casefold() == "all":
            return "all"
        if value not in {"India", "International"}:
            raise ValueError("jurisdiction must be India, International, or all")
        return value


class QueryResponse(BaseModel):
    query: str
    answer: str
    decision: Decision
    confidence: float | None
    citations: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    retrieved_evidence: list[dict[str, Any]]
    abstention_reason: str | None
    claim_verification: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]


app = FastAPI(title="IP-SAKTI Sahayak RAG API", version="1.0.0")
_retriever_cache: LegalRetriever | None = None
_retriever_init_lock = Lock()
_retriever_use_lock = Lock()


@app.middleware("http")
async def request_correlation_middleware(request: Request, call_next):
    candidate_id = request.headers.get("x-request-id", "")
    request_id = candidate_id if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", candidate_id) else str(uuid4())
    request.state.request_id = request_id
    token = set_current_request_id(request_id)
    started_at = time.perf_counter()
    status_code = 500
    logger.warning(
        "RAG_REQUEST event=start request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as error:
        exception_class = type(error).__name__
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,79}", exception_class):
            exception_class = "unknown"
        logger.error(
            "RAG_REQUEST event=error request_id=%s exception_class=%s",
            request_id,
            exception_class,
        )
        raise
    finally:
        logger.warning(
            "RAG_REQUEST event=complete request_id=%s http_status=%s duration_ms=%.3f",
            request_id,
            status_code,
            (time.perf_counter() - started_at) * 1000,
        )
        reset_current_request_id(token)


def _get_shared_retriever() -> LegalRetriever:
    """Lazily initialize one retriever per worker process."""
    global _retriever_cache
    with _retriever_init_lock:
        if _retriever_cache is None:
            _retriever_cache = LegalRetriever()
        return _retriever_cache


def _retrieved_evidence(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a stable, serializable evidence view with text and source metadata."""
    evidence: list[dict[str, Any]] = []
    for rank, chunk in enumerate(chunks, start=1):
        source = _source_record(chunk)
        evidence.append({
            "rank": rank,
            "text": str(chunk.get("text") or ""),
            "source": source,
            "retrieval": {
                key: chunk.get(key)
                for key in ("hybrid_score", "dense_rank", "bm25_rank", "final_score", "query_intent")
            },
        })
    return evidence


def _is_ayurvedic_patent_follow_up(query: str) -> bool:
    return bool(re.search(r"\bpatent\b", query, re.IGNORECASE)
                and re.search(r"\bayurved\w*\b", query, re.IGNORECASE))


def _has_patentability_evidence(chunks: list[dict[str, Any]]) -> bool:
    retrieved_sections: set[str] = set()
    for chunk in chunks:
        document_id = str(chunk.get("document_id") or "").casefold()
        document_name = str(chunk.get("document_name") or "").casefold()
        provision_type = str(chunk.get("provision_type") or "").casefold().rstrip("s")
        number = str(chunk.get("provision_number") or "")
        if (("patent_act" in document_id or re.search(r"patents?\s+act", document_name))
                and provision_type == "section" and number in {"2", "3"}):
            retrieved_sections.add(number)
    return {"2", "3"}.issubset(retrieved_sections)


def _response(
    *, query: str, answer: str, decision: Decision, chunks: list[dict[str, Any]],
    confidence: float | None = None, citations: list[dict[str, Any]] | None = None,
    abstention_reason: str | None = None,
    claim_verification: dict[str, Any] | None = None,
) -> QueryResponse:
    response_started = time.perf_counter()
    sources = [_source_record(chunk) for chunk in chunks]
    response = QueryResponse(
        query=query,
        answer=answer,
        decision=decision,
        confidence=confidence,
        citations=citations or [],
        sources=sources,
        retrieved_evidence=_retrieved_evidence(chunks),
        abstention_reason=abstention_reason,
        claim_verification=claim_verification,
    )
    _log_stage_duration("response_construction", response_started)
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report process health without initializing retrieval or generation clients."""
    return HealthResponse(status="ok")


@app.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest) -> QueryResponse:
    """Run query analysis, retrieval, guard, generation, and existing validators."""
    logger.warning("RAG_STAGE_TIMING request_id=%s stage=query_endpoint_entered", current_request_id())
    query = request.query
    # LegalRetriever performs the existing deterministic query-intent analysis internally.
    retriever_started = time.perf_counter()
    try:
        retriever = _get_shared_retriever()
    finally:
        _log_stage_duration("retriever_construction", retriever_started)
    retrieval_started = time.perf_counter()
    try:
        # Serialize access to shared retrieval objects and last_retrieval_debug;
        # keep generation outside the lock.
        with _retriever_use_lock:
            chunks = retriever.retrieve(query, get_top_k(), jurisdiction=request.jurisdiction)
    finally:
        _log_stage_duration("retrieval_total", retrieval_started)

    guard = evaluate_abstention_guard(query)
    if guard.should_abstain:
        result = build_rag_result(query, guard.explanation, chunks)
        return _response(
            query=query,
            answer=result["answer"],
            decision="abstain",
            chunks=chunks,
            abstention_reason=f"{guard.category}: {guard.explanation}",
        )

    missing_evidence = None
    if not chunks:
        missing_evidence = (
            "No relevant legal source was retrieved, so this answer cannot be supported."
        )
    elif (_is_ayurvedic_patent_follow_up(query)
          and not _has_patentability_evidence(chunks)):
        missing_evidence = (
            "The retrieved sources do not include the Patents Act provisions defining invention "
            "and setting its statutory exclusions. Without those provisions, and product details "
            "such as the proposed composition or process and evidence of novelty or inventive step, "
            "I cannot assess patentability."
        )
    if missing_evidence:
        result = build_rag_result(query, missing_evidence, chunks)
        return _response(
            query=query,
            answer=result["answer"],
            decision="abstain",
            chunks=chunks,
            abstention_reason=missing_evidence,
        )

    llm = None
    try:
        llm = OllamaClient()
        generated_answer = _generate_grounded_answer(query, chunks, llm)
    except Exception as error:
        # Log only bounded identifiers/status metadata; never log exception text or request data.
        logger.error(
            "RAG generation failed request_id=%s %s",
            current_request_id(),
            json.dumps(_generation_failure_diagnostics(error, llm), separators=(",", ":")),
        )
        safe_message = "Answer generation failed. Please try again later."
        result = build_rag_result(query, safe_message, chunks)
        return _response(
            query=query,
            answer=result["answer"],
            decision="generation_error",
            chunks=chunks,
        )

    citation_started = time.perf_counter()
    validation = validate_citations(generated_answer, chunks)
    _log_stage_duration("citation_validation", citation_started)
    claim_started = time.perf_counter()
    try:
        claim_verification = verify_claims(generated_answer, chunks)
    finally:
        _log_stage_duration("claim_verification", claim_started)
    confidence_started = time.perf_counter()
    confidence_result = score_confidence(query, chunks, validation)
    if (confidence_result["decision"] == "answer"
            and claim_verification.get("unsupported_claims", 0) > 0):
        confidence_result = dict(confidence_result)
        confidence_result["decision"] = "answer_with_caution"
        confidence_result["reasons"] = [
            *confidence_result.get("reasons", []),
            "One or more claims lack a validated evidence citation.",
        ]
    displayed_answer = apply_confidence_decision(generated_answer, confidence_result)
    _log_stage_duration("confidence_and_decision_formatting", confidence_started)
    result = build_rag_result(
        query, displayed_answer, chunks, validation, confidence_result, generated_answer
    )
    return _response(
        query=query,
        answer=result["answer"],
        decision=confidence_result["decision"],
        confidence=float(confidence_result["score"]),
        chunks=chunks,
        citations=validation.get("citations", []),
        abstention_reason=(
            "; ".join(confidence_result.get("reasons", []))
            if confidence_result["decision"] == "abstain" else None
        ),
        claim_verification=claim_verification,
    )
