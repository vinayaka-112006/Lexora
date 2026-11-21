"""Deterministic claim-to-citation coverage checks; semantic support is not inferred."""
from __future__ import annotations

import re
from typing import Any

from app.citation_validator import validate_citations

_CITATION_MARKER = re.compile(r"\[\s*Source\s*:[^\]\n]*(?:\]|$)", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[\"'])")
_HEADING = re.compile(r"^\s{0,3}(?:#{1,6}\s+.+|(?:answer|summary|analysis|conclusion|sources?)\s*:)\s*$", re.IGNORECASE)


def _without_citations(text: str) -> str:
    """Remove citation labels to leave the original claim wording."""
    return _CITATION_MARKER.sub("", text).strip()


def _is_citation_only(text: str) -> bool:
    """Return whether a fragment contains only one or more source markers."""
    stripped = _CITATION_MARKER.sub("", text)
    return bool(_CITATION_MARKER.search(text)) and not stripped.strip(" \t,;.")


def _split_fragments(answer: str) -> list[str]:
    """Split non-heading answer lines into sentence-like fragments."""
    fragments: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip()
        if not stripped or _HEADING.match(stripped):
            continue
        citations = _CITATION_MARKER.findall(stripped)
        citation_indices = iter(range(len(citations)))
        protected = _CITATION_MARKER.sub(lambda match: f" CITATIONTOKEN{next(citation_indices)} ", stripped)
        parts = [part.strip() for part in _SENTENCE_SPLIT.split(protected) if part.strip()]
        for part in parts:
            for index, citation in enumerate(citations):
                part = part.replace(f"CITATIONTOKEN{index}", citation)
            fragments.append(part)
    return fragments


def extract_claims(answer: str) -> list[dict[str, Any]]:
    """Extract claim-like sentence units and attach citation-only continuation lines."""
    claims: list[dict[str, Any]] = []
    for fragment in _split_fragments(answer):
        if _is_citation_only(fragment):
            if claims:
                claims[-1]["citation_text"] += " " + fragment
            continue
        claim_text = _without_citations(fragment)
        if not claim_text:
            continue
        claims.append({"claim_id": len(claims) + 1, "text": claim_text, "citation_text": fragment})
    return claims


def verify_claims(answer: str, retrieved_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Report citation/evidence coverage per claim without asserting semantic support.

    A valid citation matched to retrieved chunk metadata yields ``uncertain`` because
    deterministic metadata checks cannot establish that evidence entails the claim.
    """
    extracted = extract_claims(answer)
    claims: list[dict[str, Any]] = []
    for item in extracted:
        validation = validate_citations(item["citation_text"], retrieved_chunks)
        citations = validation["citations"]
        valid_citations = [citation for citation in citations if citation["valid"]]
        citation_valid = bool(valid_citations)
        evidence_found = any(citation.get("matched_chunk_ids") for citation in valid_citations)
        status = "uncertain" if citation_valid and evidence_found else "unsupported"
        claims.append({
            "claim_id": item["claim_id"],
            "text": item["text"],
            "citations": [citation["raw"] for citation in citations],
            "status": status,
            "citation_valid": citation_valid,
            "evidence_found": evidence_found,
            "semantic_support": "not_verified",
            "citation_results": citations,
        })

    count = len(claims)
    covered = sum(1 for claim in claims if claim["citation_valid"] and claim["evidence_found"])
    if covered == count and count > 0:
        overall = "complete_citation_coverage"
    elif covered:
        overall = "partial_citation_coverage"
    else:
        overall = "insufficient_citation_coverage"
    return {
        "claim_count": count,
        "supported_claims": 0,
        "uncertain_claims": sum(claim["status"] == "uncertain" for claim in claims),
        "unsupported_claims": sum(claim["status"] == "unsupported" for claim in claims),
        "citation_coverage": round(covered / count, 4) if count else 0.0,
        "overall_status": overall,
        "semantic_support": "not_verified",
        "claims": claims,
    }



