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
from app.answer_postprocessor import postprocess_generated_answer
from app.llm_client import (
    IncompleteGenerationError,
    OllamaClient,
    current_request_id,
    groq_key_configuration_diagnostics,
    reset_current_request_id,
    set_current_request_id,
)
from app.main import _generate_grounded_answer, _source_record, build_rag_result
from app.retriever import (
    LegalRetriever, analyze_legal_query, explicit_provision_diagnostic, get_top_k,
)
from app.router import RouteDecision, route_query

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

Decision = Literal["answer", "answer_with_caution", "abstain", "generation_error", "generation_incomplete", "general", "clarification"]


class HistoryEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["user", "assistant"] = "user"
    content: str = ""
    text: str = ""


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    jurisdiction: str | None = None
    history: list[HistoryEntry] | None = None

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
    retrieval_diagnostic: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    generation_metadata: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    mode: Literal["general", "legal", "clarification"] = "legal"


class HealthResponse(BaseModel):
    status: Literal["ok"]


app = FastAPI(title="IP-SAKTI Sahayak RAG API", version="1.0.0")
_retriever_cache: LegalRetriever | None = None
_retriever_init_lock = Lock()
_retriever_use_lock = Lock()


def _deterministic_general_reply(query: str, routing: RouteDecision) -> str | None:
    """Return an instant, natural response for obvious greetings and pleasantries."""
    q = query.strip().lower()
    if re.fullmatch(r"(?:hello|hi|hey|hiya|greetings)(?:\s+(?:there|all))?[!.]*", q):
        return "Hello! How can I help you today?"
    if re.fullmatch(r"good\s+(morning|afternoon|evening|day)[!.]*", q):
        m = re.match(r"good\s+(morning|afternoon|evening|day)", q)
        time_of_day = m.group(1) if m else "day"
        return f"Good {time_of_day}! How can I help you today?"
    if re.fullmatch(r"(?:how\s+are\s+you(?:\s+doing)?|how\s+is\s+it\s+going|how\s+do\s+you\s+do)[!.,?]*", q):
        return "I'm doing well, thank you! How can I assist you with your research or questions today?"
    if re.fullmatch(r"(?:thank\s+you(?:\s+(?:so\s+much|very\s+much|a\s+lot))?|thanks(?:\s+(?:a\s+lot|so\s+much))?|thx)[!.]*", q):
        return "You're very welcome! Let me know if you have any other questions."
    if re.fullmatch(r"(?:bye(?:[!\s]+bye)?|goodbye|see\s+you(?:\s+later)?|have\s+a\s+(?:good|great|nice)\s+day)[!.]*", q):
        return "Goodbye! Have a great day!"
    if re.fullmatch(r"(?:who\s+are\s+you|what\s+is\s+your\s+name|what\s+can\s+you\s+do)[!.,?]*", q):
        return (
            "I am IP-SAKTI Sahayak, an AI research assistant specializing in Indian intellectual property, "
            "biodiversity regulation, and traditional knowledge for Ayurvedic startups, researchers, and practitioners."
        )
    return None


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


def _missing_explicit_provisions(
    query: str, chunks: list[dict[str, Any]], chunk_catalog: dict[str, dict[str, Any]] | None = None
) -> list[dict[str, str]]:
    """Return requested provision references not represented in retrieved evidence."""
    diagnostic = explicit_provision_diagnostic(query, chunks, chunk_catalog)
    return diagnostic["missing"] if diagnostic else []


def _response(
    *, query: str, answer: str, decision: Decision, chunks: list[dict[str, Any]],
    confidence: float | None = None, citations: list[dict[str, Any]] | None = None,
    abstention_reason: str | None = None,
    claim_verification: dict[str, Any] | None = None,
    retrieval_diagnostic: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    generation_metadata: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
    mode: Literal["general", "legal", "clarification"] = "legal",
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
        retrieval_diagnostic=retrieval_diagnostic,
        warnings=warnings or [],
        generation_metadata=generation_metadata,
        diagnostics=diagnostics,
        mode=mode,
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

    # Extract recent conversation history if provided
    history_records: list[dict[str, str]] = []
    if request.history:
        for item in request.history[-6:]:
            msg_text = (item.content or item.text or "").strip()
            if msg_text:
                history_records.append({"role": item.role, "content": msg_text})

    # 1. Hybrid Intent Router: General vs Legal vs Clarification
    routing = route_query(query, history=history_records if history_records else None)

    if routing.mode == "clarification":
        clarification_started = time.perf_counter()
        _log_stage_duration("clarification_mode_routed", clarification_started)
        clarification_text = routing.clarification_question or (
            "Could you please clarify your question? For example, are you asking about intellectual property / patentability, "
            "regulatory compliance (such as the Biological Diversity Act or Ayush/FSSAI rules), or general information?"
        )
        return _response(
            query=query,
            answer=clarification_text,
            decision="clarification",
            chunks=[],
            confidence=1.0,
            mode="clarification",
            diagnostics={"mode": "clarification", "routing_reason": routing.reason, "execution": "clarification"},
        )

    if routing.mode == "general":
        general_started = time.perf_counter()
        _log_stage_duration("general_mode_routed", general_started)

        # Fast deterministic path for standard greetings & pleasantries
        deterministic_reply = _deterministic_general_reply(query, routing)
        if deterministic_reply:
            _log_stage_duration("general_mode_generation", general_started)
            return _response(
                query=query,
                answer=deterministic_reply,
                decision="general",
                chunks=[],
                confidence=1.0,
                mode="general",
                diagnostics={"mode": "general", "routing_reason": routing.reason, "execution": "deterministic"},
            )

        # General conversation via direct LLM call (bypassing Chroma, embeddings, BM25, RRF, legal validators)
        try:
            llm = OllamaClient()
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are IP-SAKTI Sahayak, a helpful and friendly AI assistant for Ayurvedic researchers, "
                        "startups, and practitioners. Answer the user's inquiry naturally, politely, and informatively. "
                        "Do not cite statutory sections or insert legal disclaimers for ordinary conversation."
                    ),
                },
            ]
            if history_records:
                for msg in history_records[-4:]:
                    messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": query})
            answer = llm.generate(messages).strip()
            _log_stage_duration("general_mode_generation", general_started)
            return _response(
                query=query,
                answer=answer,
                decision="general",
                chunks=[],
                confidence=1.0,
                mode="general",
                diagnostics={"mode": "general", "routing_reason": routing.reason, "execution": "direct_llm"},
            )
        except Exception as error:
            logger.warning("General LLM generation failed, using safe fallback: %s", error)
            fallback = "Hello! I am IP-SAKTI Sahayak. How can I help you today?"
            return _response(
                query=query,
                answer=fallback,
                decision="general",
                chunks=[],
                confidence=1.0,
                mode="general",
                diagnostics={"mode": "general", "routing_reason": routing.reason, "execution": "fallback"},
            )

    diagnostics_enabled = os.getenv("RAG_DEBUG_TRACE", "").strip().casefold() in {"1", "true", "yes", "on"}
    trace: dict[str, Any] | None = None
    if diagnostics_enabled:
        trace = {
            "original_question": query,
            "normalized_question": query,
            "query_analysis": analyze_legal_query(query),
            "jurisdiction_input": request.jurisdiction,
            "mode": "legal",
            "routing_reason": routing.reason,
        }

    # For contextual follow-up legal queries without embedded Context: header,
    # enrich the retrieval query with the previous user topic so retriever finds relevant sections
    retrieval_query = query
    if routing.is_follow_up and history_records and not re.search(r"\bContext:", query, re.I):
        for msg in reversed(history_records):
            if msg.get("role") == "user" and msg.get("content"):
                retrieval_query = f"{query}\n\nContext: original question: {msg['content']}"
                break

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
            chunks = retriever.retrieve(retrieval_query, get_top_k(), jurisdiction=request.jurisdiction)
            if trace is not None:
                trace["retrieval_debug"] = dict(getattr(retriever, "last_retrieval_debug", {}))
                trace["retrieval_trace"] = dict(getattr(retriever, "last_retrieval_trace", {}))
    finally:
        _log_stage_duration("retrieval_total", retrieval_started)
    retrieval_diagnostic = explicit_provision_diagnostic(
        retrieval_query, chunks, getattr(retriever, "chunks", None)
    )

    guard = evaluate_abstention_guard(retrieval_query)
    if guard.should_abstain:
        result = build_rag_result(query, guard.explanation, chunks)
        return _response(
            query=query,
            answer=result["answer"],
            decision="abstain",
            chunks=chunks,
            abstention_reason=f"{guard.category}: {guard.explanation}",
            retrieval_diagnostic=retrieval_diagnostic,
            diagnostics=trace,
        )

    missing_evidence = None
    if not chunks:
        missing_evidence = (
            "No relevant legal source was retrieved, so this answer cannot be supported."
        )
    elif (_is_ayurvedic_patent_follow_up(retrieval_query)
          and not _has_patentability_evidence(chunks)):
        missing_evidence = (
            "The retrieved sources do not include the Patents Act provisions defining invention "
            "and setting its statutory exclusions. Without those provisions, and product details "
            "such as the proposed composition or process and evidence of novelty or inventive step, "
            "I cannot assess patentability."
        )
    missing_provisions = _missing_explicit_provisions(
        retrieval_query, chunks, getattr(retriever, "chunks", None)
    )
    if missing_provisions:
        missing_labels = ", ".join(
            f"{item['type']} {item['number']}" for item in missing_provisions
        )
        missing_evidence = (
            f"The retrieved evidence does not include the explicitly requested {missing_labels}. "
            "I cannot complete the requested provision-by-provision explanation from the available sources."
        )
    if missing_evidence:
        result = build_rag_result(query, missing_evidence, chunks)
        return _response(
            query=query,
            answer=result["answer"],
            decision="abstain",
            chunks=chunks,
            abstention_reason=missing_evidence,
            retrieval_diagnostic=retrieval_diagnostic,
            diagnostics=trace,
        )

    llm = None
    try:
        llm = OllamaClient()
        if trace is not None:
            generated_answer = _generate_grounded_answer(query, chunks, llm, diagnostics=trace)
        else:
            generated_answer = _generate_grounded_answer(query, chunks, llm)
    except Exception as error:
        # Log only bounded identifiers/status metadata; never log exception text or request data.
        logger.error(
            "RAG generation failed request_id=%s %s",
            current_request_id(),
            json.dumps(_generation_failure_diagnostics(error, llm), separators=(",", ":")),
        )
        if isinstance(error, IncompleteGenerationError):
            safe_message = "Generation stopped before completion. This response is incomplete and has not been verified."
            result = build_rag_result(query, safe_message, chunks)
            return _response(
                query=query,
                answer=result["answer"],
                decision="generation_incomplete",
                chunks=chunks,
                retrieval_diagnostic=retrieval_diagnostic,
                generation_metadata=error.metadata,
                diagnostics=trace,
                warnings=["Partial model output was withheld because generation did not complete and was not verified."],
                claim_verification={
                    "claim_count": 0,
                    "supported_claims": 0,
                    "uncertain_claims": 0,
                    "unsupported_claims": 0,
                    "withheld_claim_count": None,
                    "citation_coverage": None,
                    "overall_status": "not_evaluated_incomplete_generation",
                    "semantic_support": "not_verified",
                    "claims": [],
                },
            )
        safe_message = "Answer generation failed. Please try again later."
        result = build_rag_result(query, safe_message, chunks)
        return _response(
            query=query,
            answer=result["answer"],
            decision="generation_error",
            chunks=chunks,
            retrieval_diagnostic=retrieval_diagnostic,
        )

    postprocess_started = time.perf_counter()
    processed = postprocess_generated_answer(query, generated_answer, chunks)
    validation = processed["validation"]
    claim_verification = processed["claim_verification"]
    confidence_result = processed["confidence"]
    displayed_answer = processed["answer"]
    _log_stage_duration("citation_claim_confidence_postprocessing", postprocess_started)
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
        retrieval_diagnostic=retrieval_diagnostic,
        warnings=processed["warnings"],
        generation_metadata=getattr(llm, "last_generation_metadata", None),
        diagnostics=(
            {**(trace or {}), "claim_verification": claim_verification,
             "citation_validation": validation, "postprocessing_warnings": processed["warnings"]}
            if trace is not None else None
        ),
    )



# 6. Complete function and class summary
# Function / class	Main purpose
# _log_stage_duration()	Logs execution time.
# _safe_log_component()	Sanitizes diagnostic values.
# _generation_failure_diagnostics()	Collects safe LLM error information.
# QueryRequest	Defines and validates incoming requests.
# query_must_contain_non_whitespace()	Rejects blank questions.
# validate_jurisdiction()	Validates jurisdiction.
# QueryResponse	Defines the outgoing response structure.
# HealthResponse	Defines health-check response.
# _deterministic_general_reply()	Handles common greetings without an LLM call.
# request_correlation_middleware()	Tracks HTTP requests and request IDs.
# _get_shared_retriever()	Initializes and reuses the retriever.
# _retrieved_evidence()	Formats retrieved evidence for the frontend.
# _is_ayurvedic_patent_follow_up()	Identifies Ayurvedic patent questions.
# _has_patentability_evidence()	Checks for Patents Act Sections 2 and 3.
# _missing_explicit_provisions()	Identifies requested but missing provisions.
# _response()	Constructs a standardized API response.
# health()	Checks whether the API process responds.
# query_endpoint()	Controls the complete frontend question-answering process.

# 7. Difference between main.py and api.py
# This is particularly important for understanding your project.
# main.py	api.py
# Command-line application	FastAPI application
# Takes questions through terminal input	Takes questions through HTTP requests
# Uses input()	Uses QueryRequest
# Prints answers using print()	Returns JSON responses
# Calls _handle_question()	Calls query_endpoint()
# Useful for terminal testing	Used by the frontend

# One important architectural observation: Both files reuse the same core RAG components, but they are separate entry points. api.py imports functions from main.py; it does not call main() or run the CLI loop.

# Also, the main.py CLI flow and api.py flow are not identical. For example, the API has general/legal routing and additional patentability evidence checks.

# What you should remember from api.py
# There are three particularly important things:
# 1. QueryRequest and QueryResponse: Define how the frontend communicates with the backend.
# 2. request_correlation_middleware(): Handles request tracking and logging.
# 3. query_endpoint(): Controls the complete API question-answering process.
# If you understand these three, you understand the fundamental purpose of api.py.