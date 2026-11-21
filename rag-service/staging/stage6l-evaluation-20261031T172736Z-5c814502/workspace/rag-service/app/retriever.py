"""Hybrid dense and BM25 retrieval with explainable legal query intent hints."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from chroma_config import (
    DEFAULT_CHROMA_PATH,
    DEFAULT_CHUNKS_PATH,
    resolve_chunks_path,
    resolve_index_paths,
)
from app.llm_client import current_request_id
from app.query_morphology import conditionally_expand_query, morphology_vocabulary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


def _log_stage_duration(stage: str, started_at: float) -> None:
    logger.warning(
        "RAG_STAGE_TIMING request_id=%s stage=%s elapsed_ms=%.3f",
        current_request_id(),
        stage,
        (time.perf_counter() - started_at) * 1000,
    )
CHROMA_PATH = DEFAULT_CHROMA_PATH
CHUNKS_PATH = DEFAULT_CHUNKS_PATH
COLLECTION_NAME = "ip_sakti_legal"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MORPHOLOGY_EXPANSION_ENV = "MORPHOLOGY_EXPANSION_ENABLED"
METADATA_FIELDS = (
    "document_id", "document_name", "filename", "jurisdiction", "provision_type",
    "provision_number", "provision_title", "chapter_or_part", "subsection_path",
    "page_start", "page_end", "source_pages", "extraction_methods", "content_type",
)
INTENT_EXPANSIONS = {
    "definition": ("definition", "means", "meaning", "defined"),
    "purpose": ("purpose", "objective", "aims", "objectives", "implementation"),
    "prohibition": ("excluded", "not an invention", "patentability", "prohibited", "shall not", "cannot"),
}
MARK_QUERY_PATTERN = re.compile(r"\b(?:marks?|trade[\s-]?marks?)\b", re.IGNORECASE)
DOCUMENT_REFERENCE_STOPWORDS = {
    "a", "an", "and", "article", "articles", "does", "for", "in", "of", "section",
    "sections", "say", "the", "to", "under", "what",
}


def _mark_related_query(query: str) -> bool:
    """Return whether the user explicitly asks about marks or trademarks."""
    return bool(MARK_QUERY_PATTERN.search(query))


def _document_reference_tokens(value: str, *, query: bool = False) -> list[str]:
    """Normalize query/document-name tokens for exact metadata phrase matching."""
    tokens = re.findall(r"[a-z]+|\d+", value.casefold())
    normalized: list[str] = []
    for token in tokens:
        if token.isdigit():
            # Document names often include publication years omitted by users.
            continue
        if token == "the" or (query and token in DOCUMENT_REFERENCE_STOPWORDS):
            continue
        if token.endswith("ies") and len(token) > 4:
            token = f"{token[:-3]}y"
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            token = token[:-1]
        normalized.append(token)
    return normalized


def _named_document_id(query: str, chunks: dict[str, dict[str, Any]]) -> str | None:
    """Resolve one explicitly named document from the existing chunk metadata.

    Matching uses a normalized document_name phrase already present in chunks.json.
    Ambiguous or unmatched names return None and retain the existing unscoped bonus.
    """
    query_tokens = _document_reference_tokens(query, query=True)
    if not query_tokens:
        return None
    matched_ids: set[str] = set()
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for chunk in chunks.values():
        document_id = str(chunk.get("document_id") or "")
        document_name = str(chunk.get("document_name") or "")
        name_tokens = tuple(_document_reference_tokens(document_name))
        identity = (document_id, name_tokens)
        if not document_id or len(name_tokens) < 2 or identity in seen:
            continue
        seen.add(identity)
        width = len(name_tokens)
        if any(query_tokens[index:index + width] == list(name_tokens)
               for index in range(len(query_tokens) - width + 1)):
            matched_ids.add(document_id)
    return next(iter(matched_ids)) if len(matched_ids) == 1 else None


def _positive_env(name: str, default: int) -> int:
    """Read a positive integer setting from the environment."""
    value = os.getenv(name, str(default))
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if number < 1:
        raise ValueError(f"{name} must be a positive integer")
    return number


def _nonnegative_env(name: str, default: float) -> float:
    """Read a nonnegative score bonus from the environment."""
    value = os.getenv(name, str(default))
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a nonnegative number") from error
    if number < 0:
        raise ValueError(f"{name} must be a nonnegative number")
    return number


def _morphology_enabled() -> bool:
    """Read the reversible morphology feature flag (disabled unless explicitly enabled)."""
    value = os.getenv(MORPHOLOGY_EXPANSION_ENV, "false").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"{MORPHOLOGY_EXPANSION_ENV} must be true or false")


def get_top_k() -> int:
    """Return the final hybrid result count (TOP_K remains a compatibility fallback)."""
    return _positive_env("FINAL_TOP_K", 5) if "FINAL_TOP_K" in os.environ else _positive_env("TOP_K", 5)


def _decode_list(value: Any) -> Any:
    """Decode list metadata serialized by Stage 3 for Chroma."""
    if not isinstance(value, str) or not value:
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _stable_chunk_id(chunk: dict[str, Any]) -> str:
    """Use Stage 3's deterministic Chroma identity scheme."""
    identity = f"{chunk.get('document_id') or ''}#chunk-{chunk.get('chunk_index')}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def load_chunk_map(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load and validate a configured chunk map without opening Chroma."""
    resolved_path = resolve_chunks_path(path)
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Chunk map was not found: {resolved_path}")
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"Malformed chunk-map JSON at {resolved_path}: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("chunks"), list):
        raise ValueError(f"Chunk map at {resolved_path} must be an object containing a 'chunks' list")
    chunks = payload["chunks"]
    if not chunks:
        raise ValueError(f"Chunk map at {resolved_path} contains no chunks")
    stable_ids: set[str] = set()
    source_ids: set[str] = set()
    for position, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk map record {position} in {resolved_path} is not an object")
        document_id = chunk.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip() or chunk.get("chunk_index") is None:
            raise ValueError(f"Chunk map record {position} in {resolved_path} needs document_id and chunk_index")
        if not isinstance(chunk.get("text"), str) or not chunk["text"].strip():
            raise ValueError(f"Chunk map record {position} in {resolved_path} has no usable text")
        stable_id = _stable_chunk_id(chunk)
        if stable_id in stable_ids:
            raise ValueError(f"Duplicate document_id/chunk_index identity in chunk map at record {position}: {stable_id}")
        stable_ids.add(stable_id)
        source_id = chunk.get("chunk_id")
        if source_id is not None:
            if not isinstance(source_id, str) or not source_id.strip():
                raise ValueError(f"Chunk map record {position} in {resolved_path} has an invalid chunk_id")
            if source_id in source_ids:
                raise ValueError(f"Duplicate chunk_id in chunk map at record {position}: {source_id}")
            source_ids.add(source_id)
    return chunks


def _tokenize(text: str) -> list[str]:
    """Retain legal words, numbers, and adjacent terms for simple phrase matching."""
    words = re.findall(r"[a-z0-9]+", text.casefold())
    expanded = list(words)
    expanded.extend("trademark" for word in words if word == "trademarks")
    expanded.extend(
        "trademark" for left, right in zip(words, words[1:])
        if left == "trade" and right in {"mark", "marks"}
    )
    return expanded + [f"{left}_{right}" for left, right in zip(words, words[1:])]


def analyze_legal_query(query: str) -> dict[str, Any]:
    """Classify broad legal query intent and extract only explicit provision references."""
    normalized = query.casefold()
    explicit_match = re.search(
        r"\b(section|sections|article|articles|rule|rules|regulation|regulations)\s+(\d+[a-z]*(?:\([a-z0-9]+\))?)(?![a-z0-9])",
        normalized,
    )
    explicit = None
    if explicit_match:
        explicit = {
            "type": (
                "section" if explicit_match.group(1).startswith("section") else
                "article" if explicit_match.group(1).startswith("article") else
                "regulation" if explicit_match.group(1).startswith("regulation") else "rule"
            ),
            "number": explicit_match.group(2),
        }
    comparison = any(term in normalized for term in (
        "compare", "comparison", "difference between", " versus ", " vs ",
        "indian and international", "under indian law and", "compared with",
    ))
    if comparison:
        intent = "comparison"
    elif explicit:
        intent = "explicit_provision"
    elif any(term in normalized for term in ("purpose", "objective", "objectives", "aim", "aims", "why was")):
        intent = "purpose"
    elif any(term in normalized for term in (
        "not an invention", "not inventions", "excluded from patentability", "prohibited",
        "cannot be patented", "cannot patent", "barred", "not eligible", "shall not",
    )):
        intent = "prohibition"
    elif any(term in normalized for term in (
        "what is", "what are", "define", "definition", "meaning", " means ",
    )):
        intent = "definition"
    else:
        intent = "general"

    jurisdictions: list[str] = []
    india_requested = bool(re.search(r"\bindia(?:n)?\b", normalized))
    international_requested = bool(re.search(
        r"\b(international|global|treaty|protocol|convention|cross[- ]border)\b", normalized
    ))
    if india_requested:
        jurisdictions.append("India")
    if international_requested:
        jurisdictions.append("International")
    keywords = list(dict.fromkeys(_tokenize(query)))
    keywords.extend(term for term in INTENT_EXPANSIONS.get(intent, ()) if term not in keywords)
    if intent == "definition" and _mark_related_query(query) and "mark" not in keywords:
        keywords.append("mark")
    return {
        "intent": intent,
        "explicit_provision": explicit,
        "jurisdictions_requested": jurisdictions,
        "keywords": keywords,
    }


def _legacy_definition_query(query: str) -> str:
    """Preserve the previous generic expansion for an unadjusted baseline."""
    normalized = query.casefold().strip()
    if (normalized.startswith(("what is ", "define ", "meaning of "))
            or normalized.endswith(" mean?")) and not any(
                term in normalized for term in ("purpose", "objective", "aim")
            ):
        return f"{query} definition meaning means"
    return query

def _jurisdiction_filter(value: str | None) -> str:
    """Resolve an explicit filter or JURISDICTION environment setting."""
    jurisdiction = (value if value is not None else os.getenv("JURISDICTION", "all")).strip()
    if jurisdiction.casefold() == "all":
        return "all"
    if jurisdiction not in {"India", "International"}:
        raise ValueError("JURISDICTION must be all, India, or International")
    return jurisdiction


def _public_result(chunk_id: str, text: str, metadata: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Return chunk text and complete Stage 2 metadata for downstream citation."""
    result = {"chunk_id": chunk_id, "text": text}
    for field in METADATA_FIELDS:
        result[field] = _decode_list(metadata.get(field))
    result.update(extra)
    return result


def _normalized_provision_number(value: Any) -> str:
    """Normalize spaces and case without changing section/article identity."""
    return re.sub(r"\s+", "", str(value or "")).casefold()


class LegalRetriever:
    """Retrieve legal chunks through Chroma, BM25, RRF, and small intent hints."""

    def __init__(
        self,
        chroma_path: Path | str | None = None,
        collection_name: str = COLLECTION_NAME,
        embedding_model: str | None = None,
        chunks_path: Path | str | None = None,
    ) -> None:
        self.embedding_model_name = embedding_model or os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.chroma_path, self.chunks_path, paths_configured = resolve_index_paths(chroma_path, chunks_path)
        raw_chunks = load_chunk_map(self.chunks_path)
        try:
            from rank_bm25 import BM25Okapi
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "Retrieval needs rank-bm25, chromadb, and sentence-transformers; install rag-service/requirements.txt"
            ) from error
        self.chunks: dict[str, dict[str, Any]] = {}
        tokens: list[list[str]] = []
        for chunk in raw_chunks:
            identifier = _stable_chunk_id(chunk)
            if identifier in self.chunks:
                raise ValueError(f"Duplicate Stage 3 chunk identity: {identifier}")
            self.chunks[identifier] = chunk
            text = " ".join(str(chunk.get(key) or "") for key in (
                "text", "document_name", "provision_type", "provision_number",
                "provision_title", "chapter_or_part", "jurisdiction",
            ))
            tokens.append(_tokenize(text))
        self.chunk_ids = list(self.chunks)
        self.morphology_vocabulary = morphology_vocabulary(raw_chunks)
        self.bm25 = BM25Okapi(tokens)
        try:
            self.model = SentenceTransformer(self.embedding_model_name)
            client = chromadb.PersistentClient(path=str(self.chroma_path))
            self.collection = client.get_collection(name=collection_name)
            if paths_configured:
                stored_ids = set(self.collection.get(include=[]).get("ids", []))
                expected_ids = set(self.chunks)
                if stored_ids != expected_ids:
                    raise ValueError(
                        "Configured CHROMA_PATH and CHUNKS_PATH do not match: "
                        f"collection has {len(stored_ids)} IDs; chunk map has {len(expected_ids)} IDs"
                    )
        except Exception as error:
            raise RuntimeError(f"Could not initialize retrieval resources: {error}") from error

    def _eligible(self, chunk_id: str, jurisdiction: str) -> bool:
        chunk = self.chunks.get(chunk_id)
        return chunk is not None and (jurisdiction == "all" or chunk.get("jurisdiction") == jurisdiction)

    def retrieve_dense(
        self, query: str, top_k: int | None = None, jurisdiction: str | None = None
    ) -> list[dict[str, Any]]:
        """Return dense candidates in distance order with 1-based ranks."""
        if not query.strip():
            raise ValueError("The search query must not be empty")
        limit = _positive_env("DENSE_TOP_K", 10) if top_k is None else top_k
        if limit < 1:
            raise ValueError("top_k must be a positive integer")
        selected = _jurisdiction_filter(jurisdiction)
        where = None if selected == "all" else {"jurisdiction": selected}
        count = min(self.collection.count(), len(self.chunks))
        if not count:
            return []
        try:
            vector = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)[0]
            response = self.collection.query(
                query_embeddings=[vector.tolist()], n_results=min(limit, count),
                include=["documents", "metadatas", "distances"], where=where,
            )
        except Exception as error:
            raise RuntimeError(f"Chroma similarity search failed: {error}") from error
        rows: list[dict[str, Any]] = []
        for identifier, text, metadata, distance in zip(
            response.get("ids", [[]])[0], response.get("documents", [[]])[0],
            response.get("metadatas", [[]])[0], response.get("distances", [[]])[0],
        ):
            if not self._eligible(identifier, selected):
                continue
            merged = dict(self.chunks[identifier])
            merged.update(metadata or {})
            # The extracted source record is authoritative for the human-readable title;
            # Chroma can retain a stale filename-derived label from an earlier index.
            merged["document_name"] = self.chunks[identifier].get("document_name")
            rows.append(_public_result(identifier, text or self.chunks[identifier].get("text", ""), merged,
                                       distance=float(distance)))
        for rank, row in enumerate(rows, start=1):
            row.update({"dense_rank": rank, "bm25_rank": None, "hybrid_score": None})
        return rows

    def retrieve_bm25(
        self, query: str, top_k: int | None = None, jurisdiction: str | None = None,
        expansion_terms: tuple[str, ...] | list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return BM25 candidates, optionally appending deterministic intent terms."""
        if not query.strip():
            raise ValueError("The search query must not be empty")
        limit = _positive_env("BM25_TOP_K", 10) if top_k is None else top_k
        if limit < 1:
            raise ValueError("top_k must be a positive integer")
        selected = _jurisdiction_filter(jurisdiction)
        expanded = _legacy_definition_query(query) if expansion_terms is None else f"{query} {' '.join(expansion_terms)}"
        scores = self.bm25.get_scores(_tokenize(expanded))
        eligible = [(i, float(scores[i])) for i, cid in enumerate(self.chunk_ids) if self._eligible(cid, selected)]
        eligible.sort(key=lambda row: (-row[1], row[0]))
        results: list[dict[str, Any]] = []
        for rank, (index, score) in enumerate(eligible[:limit], start=1):
            identifier = self.chunk_ids[index]
            chunk = self.chunks[identifier]
            results.append(_public_result(identifier, str(chunk.get("text") or ""), chunk,
                                          bm25_score=score, dense_rank=None, bm25_rank=rank,
                                          hybrid_score=None))
        return results

    def _intent_bonus(
        self, chunk: dict[str, Any], intent: str, query: str | None = None
    ) -> float:
        """Apply small configurable bonuses to wording that signals the query intent."""
        title = str(chunk.get("provision_title") or "").casefold()
        text = str(chunk.get("text") or "").casefold()
        mark_query = query is not None and _mark_related_query(query)
        title_bonus = _nonnegative_env("QUERY_INTENT_TITLE_BONUS", 0.005)
        body_bonus = _nonnegative_env("QUERY_INTENT_BONUS", 0.004)
        if intent == "definition":
            if re.search(r"\b(definition|defined|meaning)\b", title):
                return title_bonus
            if mark_query and re.search(r"\b(marks?)\b", title):
                return title_bonus
            if re.search(r"\b(definition|defined|means)\b", text):
                return _nonnegative_env("QUERY_DEFINITION_SIGNAL_BONUS", 0.006)
            if re.search(r"\bmeaning\b", text):
                return body_bonus
            if mark_query and re.search(r"\b(marks?)\b", text):
                return body_bonus
        elif intent == "purpose":
            if re.search(r"\b(purpose|objective|objectives|aim|aims)\b", title):
                return title_bonus
            if re.search(r"\b(purpose|objective|objectives|aim|aims)\b", text):
                return body_bonus
        elif intent == "prohibition":
            pattern = r"\b(prohibited|shall not|not an invention|not inventions|excluded|patentability|cannot be patented)\b"
            if re.search(pattern, title):
                return title_bonus
            if re.search(pattern, text):
                return body_bonus
        return 0.0
    def retrieve(
        self, query: str, top_k: int | None = None, jurisdiction: str | None = None,
        query_aware: bool = True,
    ) -> list[dict[str, Any]]:
        """Fuse dense/BM25 ranks and optionally apply intent, exact-reference, and diversity hints."""
        final_count = get_top_k() if top_k is None else top_k
        if final_count < 1:
            raise ValueError("top_k must be a positive integer")
        analysis = analyze_legal_query(query)
        selected = _jurisdiction_filter(jurisdiction)
        if (jurisdiction is None and "JURISDICTION" not in os.environ
                and len(analysis["jurisdictions_requested"]) == 1):
            selected = analysis["jurisdictions_requested"][0]
        expansions = INTENT_EXPANSIONS.get(analysis["intent"], ()) if query_aware else None
        patent_definition_query = (
            query_aware and analysis["intent"] == "definition"
            and bool(re.search(r"\bpatent\b", query, re.IGNORECASE))
        )
        ayurvedic_patent_query = (
            query_aware
            and bool(re.search(r"\bpatent\b", query, re.IGNORECASE))
            and bool(re.search(r"\bayurved\w*|traditional knowledge\b", query, re.IGNORECASE))
        )
        if ayurvedic_patent_query:
            expansions = (*expansions, "invention", "inventive step", "industrial application",
                          "patentability", "known substance", "known efficacy",
                          "traditional knowledge", "known properties")
        if (expansions is not None and analysis["intent"] == "definition"
                and _mark_related_query(query)):
            expansions = (*expansions, "mark")
        retrieval_query, morphology_applied = conditionally_expand_query(
            query=query,
            intent=analysis["intent"],
            explicit_provision=analysis["explicit_provision"],
            vocabulary=getattr(self, "morphology_vocabulary", set()),
            enabled=_morphology_enabled(),
        )
        self.last_retrieval_debug = {
            "original_query": query,
            "retrieval_query": retrieval_query,
            "morphology_applied": morphology_applied,
        }
        candidate_count = max(final_count, _positive_env("RETRIEVAL_CANDIDATE_K", 20))
        dense_count = _positive_env("DENSE_TOP_K", candidate_count)
        bm25_count = _positive_env("BM25_TOP_K", candidate_count)
        dense_started = time.perf_counter()
        dense = self.retrieve_dense(retrieval_query, top_k=dense_count, jurisdiction=selected)
        _log_stage_duration("dense_retrieval", dense_started)
        bm25_fusion_started = time.perf_counter()
        lexical = self.retrieve_bm25(
            retrieval_query, top_k=bm25_count, jurisdiction=selected, expansion_terms=expansions
        )
        dense_by_id = {row["chunk_id"]: row for row in dense}
        lexical_by_id = {row["chunk_id"]: row for row in lexical}

        explicit = analysis["explicit_provision"] if query_aware else None
        chunks_by_id = getattr(self, "chunks", {})
        named_document_id = _named_document_id(query, chunks_by_id)
        patent_context_query = patent_definition_query or ayurvedic_patent_query
        patent_act_id = _named_document_id("Patent Act", chunks_by_id) if patent_context_query else None
        if patent_act_id:
            # Section 2 defines invention; section 3 contains patentability exclusions
            # including known substances and traditional knowledge.
            relevant_sections = {"2", "3", "4"} if patent_definition_query else {"2", "3"}
            for identifier, chunk in chunks_by_id.items():
                if (self._eligible(identifier, selected)
                    and chunk.get("document_id") == patent_act_id
                    and str(chunk.get("provision_number")) in relevant_sections
                    and str(chunk.get("provision_type") or "").casefold().rstrip("s") == "section"
                    and identifier not in dense_by_id and identifier not in lexical_by_id):
                    lexical_by_id[identifier] = _public_result(
                        identifier, str(chunk.get("text") or ""), chunk,
                        dense_rank=None, bm25_rank=None, bm25_score=None,
                    )
        if explicit:
            expected_number = _normalized_provision_number(explicit["number"])
            expected_type = explicit["type"]
            for identifier, chunk in self.chunks.items():
                if (self._eligible(identifier, selected)
                    and str(chunk.get("provision_type") or "").casefold().rstrip("s") == expected_type
                    and _normalized_provision_number(chunk.get("provision_number")) == expected_number
                    and identifier not in dense_by_id and identifier not in lexical_by_id):
                    lexical_by_id[identifier] = _public_result(
                        identifier, str(chunk.get("text") or ""), chunk,
                        dense_rank=None, bm25_rank=None, bm25_score=None,
                    )

        rrf_k = _positive_env("RRF_K", 60)
        fused: list[dict[str, Any]] = []
        for identifier in dense_by_id.keys() | lexical_by_id.keys():
            drow, brow = dense_by_id.get(identifier), lexical_by_id.get(identifier)
            drank = drow.get("dense_rank") if drow else None
            brank = brow.get("bm25_rank") if brow else None
            base = (1 / (rrf_k + drank) if drank else 0.0) + (1 / (rrf_k + brank) if brank else 0.0)
            source = drow or brow
            assert source is not None
            bonus = self._intent_bonus(source, analysis["intent"], query=query) if query_aware else 0.0
            explicit_bonus = 0.0
            named_document_bonus = 0.0
            if named_document_id and source.get("document_id") == named_document_id:
                named_document_bonus = _nonnegative_env("NAMED_DOCUMENT_BONUS", 0.05)
            patent_definition_bonus = 0.0
            if patent_act_id and source.get("document_id") == patent_act_id:
                number = str(source.get("provision_number") or "")
                priorities = (
                    {"2": 0.08, "3": 0.06, "4": 0.06} if patent_definition_query
                    else {"2": 0.05, "3": 0.08} if ayurvedic_patent_query else {}
                )
                patent_definition_bonus = priorities.get(number, 0.0)
            if explicit and str(source.get("provision_type") or "").casefold().rstrip("s") == explicit["type"]:
                if _normalized_provision_number(source.get("provision_number")) == _normalized_provision_number(explicit["number"]):
                    if named_document_id is None or source.get("document_id") == named_document_id:
                        explicit_bonus = _nonnegative_env("EXPLICIT_PROVISION_BONUS", 0.05)
            result = dict(source)
            result.update({
                "hybrid_score": base,
                "intent_bonus": bonus,
                "final_score": base + bonus + explicit_bonus + named_document_bonus + patent_definition_bonus,
                "explicit_provision_bonus": explicit_bonus,
                "named_document_bonus": named_document_bonus,
                "patent_definition_bonus": patent_definition_bonus,
                "query_intent": analysis["intent"],
                "dense_rank": drank,
                "bm25_rank": brank,
                "distance": drow.get("distance") if drow else None,
                "bm25_score": brow.get("bm25_score") if brow else None,
                "original_query": query,
                "retrieval_query": retrieval_query,
                "morphology_applied": morphology_applied,
            })
            fused.append(result)
        fused.sort(key=lambda row: (
            -row["final_score"],
            row["bm25_rank"] if row["bm25_rank"] is not None else float("inf"),
            row["dense_rank"] if row["dense_rank"] is not None else float("inf"),
            row["chunk_id"],
        ))

        if ayurvedic_patent_query and patent_act_id:
            # This follow-up asks how patentability applies to an Ayurvedic
            # product. Keep the prompt evidence on the definition and statutory
            # exclusions instead of filling its small context with unrelated Act sections.
            fused = [
                row for row in fused
                if row.get("document_id") == patent_act_id
                and str(row.get("provision_type") or "").casefold().rstrip("s") == "section"
                and str(row.get("provision_number")) in {"2", "3"}
            ]

        if query_aware and analysis["intent"] == "comparison" and selected == "all":
            requested = analysis["jurisdictions_requested"]
            if "India" in requested and "International" in requested and final_count >= 2:
                slots = min(_positive_env("COMPARISON_JURISDICTION_SLOTS", 2), max(1, final_count // 2))
                minimum_score = _nonnegative_env("COMPARISON_DIVERSITY_MIN_SCORE", 0.014)
                reserved: list[dict[str, Any]] = []
                for jurisdiction_name in ("India", "International"):
                    relevant = [row for row in fused
                                if row.get("jurisdiction") == jurisdiction_name
                                and row["final_score"] >= minimum_score]
                    reserved.extend(relevant[:slots])
                if len({row["jurisdiction"] for row in reserved}) == 2:
                    chosen_ids = {row["chunk_id"] for row in reserved}
                    for row in fused:
                        if row["chunk_id"] not in chosen_ids and len(reserved) < final_count:
                            reserved.append(row)
                            chosen_ids.add(row["chunk_id"])
                    fused = reserved
                    fused.sort(key=lambda row: (
                        -row["final_score"],
                        row["bm25_rank"] if row["bm25_rank"] is not None else float("inf"),
                        row["dense_rank"] if row["dense_rank"] is not None else float("inf"),
                        row["chunk_id"],
                    ))
        _log_stage_duration("bm25_retrieval_hybrid_fusion", bm25_fusion_started)
        return fused[:final_count]









