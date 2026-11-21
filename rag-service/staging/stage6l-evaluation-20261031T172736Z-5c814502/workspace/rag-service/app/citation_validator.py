"""Deterministically validate citation metadata against supplied retrieved chunks."""
from __future__ import annotations

import re
from typing import Any

_CITATION_START = re.compile(r"\[\s*Source\s*:", re.IGNORECASE)
_PROVISION_CITATION = re.compile(
    r"^\[\s*Source\s*:\s*(?P<document>.+?)\s*,\s*"
    r"(?P<provision_type>[A-Za-z][A-Za-z ]*?)\s+(?P<provision_number>[A-Za-z0-9()./-]+)\s*,\s*"
    r"pp?\.?\s*(?P<page_start>\d+)\s*-\s*(?P<page_end>\d+)\s*\]$",
    re.IGNORECASE,
)
_DOCUMENT_CITATION = re.compile(
    r"^\[\s*Source\s*:\s*(?P<document>.+?)\s*,\s*"
    r"pp?\.?\s*(?P<page_start>\d+)\s*-\s*(?P<page_end>\d+)\s*\]$",
    re.IGNORECASE,
)


def _normalize_label(value: Any) -> str:
    """Normalize case and whitespace while preserving semantic label content."""
    return " ".join(str(value or "").split()).casefold()


def _number(value: Any) -> int | None:
    """Convert a page value to an integer, returning None if metadata is unusable."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _citation_candidates(answer: str) -> list[str]:
    """Return every bracketed Source citation candidate, including malformed ones."""
    candidates: list[str] = []
    for match in _CITATION_START.finditer(answer):
        close = answer.find("]", match.start())
        newline = answer.find("\n", match.start())
        if close < 0 or (newline >= 0 and newline < close):
            end = newline if newline >= 0 else len(answer)
            candidates.append(answer[match.start():end].rstrip())
        else:
            candidates.append(answer[match.start():close + 1])
    return candidates


def _parse_citation(raw: str) -> dict[str, Any]:
    """Parse a citation with or without a provision reference."""
    match = _PROVISION_CITATION.fullmatch(raw)
    if match:
        fields = match.groupdict()
        return {
            "document_name": fields["document"].strip(),
            "provision_type": fields["provision_type"].strip(),
            "provision_number": fields["provision_number"].strip(),
            "page_start": int(fields["page_start"]),
            "page_end": int(fields["page_end"]),
        }
    match = _DOCUMENT_CITATION.fullmatch(raw)
    if match:
        fields = match.groupdict()
        return {
            "document_name": fields["document"].strip(),
            "provision_type": None,
            "provision_number": None,
            "page_start": int(fields["page_start"]),
            "page_end": int(fields["page_end"]),
        }
    raise ValueError("Malformed citation: expected [Source: document, provision, pp. start-end].")


def _matches_chunk(citation: dict[str, Any], chunk: dict[str, Any]) -> bool:
    """Check exact normalized source metadata and overlapping page ranges."""
    if _normalize_label(citation["document_name"]) != _normalize_label(chunk.get("document_name")):
        return False
    cited_type = citation.get("provision_type")
    cited_number = citation.get("provision_number")
    chunk_number = chunk.get("provision_number")
    if cited_type is None:
        # A document-only citation must refer to a chunk without a numbered provision.
        if chunk_number not in (None, ""):
            return False
    else:
        if _normalize_label(cited_type) != _normalize_label(chunk.get("provision_type")):
            return False
        if _normalize_label(cited_number) != _normalize_label(chunk_number):
            # A chunk may contain a whole section while a citation identifies a
            # subsection/clause inside it. Accept that narrower reference only when
            # each cited parenthetical identifier appears in order in the chunk text.
            cited_path = re.fullmatch(r"(\d+)((?:\([A-Za-z0-9ivxlcdm]+\))+)", cited_number)
            if (cited_path is None
                    or _normalize_label(cited_path.group(1)) != _normalize_label(chunk_number)):
                return False
            identifiers = re.findall(r"\(([^)]+)\)", cited_path.group(2))
            text = str(chunk.get("text") or "")
            position = 0
            for identifier in identifiers:
                match = re.search(rf"\(\s*{re.escape(identifier)}\s*\)", text[position:], re.IGNORECASE)
                if match is None:
                    return False
                position += match.end()
    chunk_start = _number(chunk.get("page_start"))
    chunk_end = _number(chunk.get("page_end"))
    if chunk_start is None or chunk_end is None or chunk_start > chunk_end:
        return False
    return citation["page_start"] <= chunk_end and citation["page_end"] >= chunk_start


def validate_citations(answer: str, retrieved_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate all answer citations against only the supplied retrieved evidence.

    This checks citation integrity, not whether the cited text supports the answer's claims.
    """
    citation_results: list[dict[str, Any]] = []
    top_errors: list[str] = []
    for raw in _citation_candidates(answer):
        result: dict[str, Any] = {"raw": raw, "valid": False, "matched_chunk_ids": [], "errors": []}
        try:
            parsed = _parse_citation(raw)
            result.update(parsed)
            if parsed["page_start"] > parsed["page_end"]:
                raise ValueError("Malformed citation: page_start must not exceed page_end.")
        except ValueError as error:
            result["errors"].append(str(error))
        else:
            matching_chunks = [chunk for chunk in retrieved_chunks if _matches_chunk(parsed, chunk)]
            if matching_chunks:
                result["valid"] = True
                result["matched_chunk_ids"] = [
                    str(chunk["chunk_id"]) for chunk in matching_chunks
                    if chunk.get("chunk_id") not in (None, "")
                ]
            else:
                result["errors"].append("Citation does not match any retrieved evidence.")
        citation_results.append(result)
        top_errors.extend(result["errors"])

    total = len(citation_results)
    valid_count = sum(1 for citation in citation_results if citation["valid"])
    invalid_count = total - valid_count
    if total == 0 and answer.strip():
        top_errors.append("Answer contains text but no citations were found.")
    return {
        "valid": total > 0 and invalid_count == 0,
        "citation_count": total,
        "total_citations": total,
        "valid_citations": valid_count,
        "invalid_citations": invalid_count,
        "citation_coverage": valid_count / total if total else 0.0,
        "citations": citation_results,
        "errors": top_errors,
    }
