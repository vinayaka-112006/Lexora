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


_SECTION_HEADING_PATTERN = re.compile(
    r'(?:^|\n)\s*(?:\d+\[)?(\d+[A-Za-z]*)\.\s+([A-Z][A-Za-z\s,.-]+)[—–]'
)


def chunk_contained_provisions(chunk: dict[str, Any]) -> set[str]:
    """Return all provision numbers represented in this chunk (primary metadata + text headings)."""
    provisions: set[str] = set()
    primary = _normalize_label(chunk.get("provision_number"))
    if primary:
        provisions.add(primary)
    text = str(chunk.get("text") or "")
    for num, _ in _SECTION_HEADING_PATTERN.findall(text):
        provisions.add(_normalize_label(num))
    return provisions


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
        contained = chunk_contained_provisions(chunk)
        cited_norm = _normalize_label(cited_number)
        chunk_norm = _normalize_label(chunk_number)
        if cited_norm != chunk_norm and cited_norm not in contained:
            # A chunk may contain a whole section while a citation identifies a
            # subsection/clause inside it. Accept that narrower reference only when
            # each cited parenthetical identifier appears in order in the chunk text.
            cited_path = re.fullmatch(r"(\d+)((?:\([A-Za-z0-9ivxlcdm]+\))+)", cited_number)
            if (cited_path is None
                    or (_normalize_label(cited_path.group(1)) != chunk_norm
                        and _normalize_label(cited_path.group(1)) not in contained)):
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


# 2. Important limitations to understand
# This validator is useful, but there are some limitations worth remembering:
# 1. It does not validate legal meaning. A citation can match a retrieved chunk while the LLM makes a claim that the chunk does not support.
# 2. Document names require normalized exact matching. Minor differences in naming can cause a valid source to fail.
# 3. Page validation checks overlap, not exact page correspondence. A citation can pass even if it cites a broader page range than the chunk.
# 4. Subsection validation is text-pattern dependent. If PDF extraction formats subsection identifiers differently, a legitimate citation may fail.
# 5. No citation is treated as invalid overall. This is intentional for answers expected to contain citations, but it means general answers without citations also produce valid=False if this function is called on them.
# The distinction between citation validation and claim verification is especially important in IP-SAKTI. Your separate claim-verification logic is responsible for examining whether claims are supported; this file only checks whether the source reference points to retrieved evidence.

# Summary: citation_validator.py
# Main purpose: This file checks whether citations generated by the LLM match the legal evidence chunks returned by the retriever.

# It validates citation metadata, not the actual correctness of legal claims.
# 1. Main functions and their purposes
# Function	Purpose
# _normalize_label()	Normalizes text by removing extra spaces and ignoring case.
# _number()	Converts page numbers into integers safely.
# _citation_candidates()	Extracts all [Source: ...] citations from the answer.
# _parse_citation()	Parses citations into document name, provision and page numbers.
# chunk_contained_provisions()	Finds provision numbers in chunk metadata and text headings.
# _matches_chunk()	Checks whether a citation matches a retrieved chunk.
# validate_citations()	Main function that validates all citations and calculates statistics.

# 2. What does _matches_chunk() check?
# It performs three important checks:
# 1. Document match: Does the cited document name match the retrieved chunk?
# 2. Provision match: Does the cited section/article match the chunk's metadata or text?
# 3. Page match: Do the citation's page numbers overlap with the chunk's page range?
# All three must pass for a citation to be valid.
# 3. Complete execution flow
# LLM-generated answer

# Extract citations

# _citation_candidates()

# Parse citation metadata

# _parse_citation()

# Match against retrieved chunks

# _matches_chunk()

# Validation report

# Valid citations, invalid citations, errors and coverage


# 4. Output of validate_citations()
# Output	Meaning
# valid	Whether all found citations are valid and at least one exists
# citation_count	Total citations found
# valid_citations	Number of valid citations
# invalid_citations	Number of invalid citations
# citation_coverage	Valid citations / total citations
# citations	Individual citation validation results
# errors	Reasons for citation failures

# Example: If 4 citations are found and 3 are valid:
# \[
# \text{Coverage} = \frac{3}{4} = 0.75
# \]

# 5. Important distinction
# Citation validation	Claim verification
# Checks whether the cited source exists in retrieved evidence.	Checks whether the answer's claims are supported by evidence.
# Checks document, provision and pages.	Examines the actual claim and its supporting text.
# Implemented in citation_validator.py.	Handled by your separate claim-verification logic.

# Remember this: citation_validator.py answers the question:

# "Is the citation pointing to a valid retrieved source?"

# It does not answer:

# "Is the legal information in the answer actually correct?"

# That's the next important part of understanding your RAG pipeline: claim_verifier.py.