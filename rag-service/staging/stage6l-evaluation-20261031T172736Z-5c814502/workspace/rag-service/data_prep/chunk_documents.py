"""Build legal provision-aware chunks from Stage 1 extracted page text."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = PROJECT_ROOT / "rag-service" / "data" / "extracted_documents.json"
OUTPUT_PATH = PROJECT_ROOT / "rag-service" / "data" / "chunks.json"
MAX_CHUNK_CHARS = 6000
LOGGER = logging.getLogger("chunk_documents")
FSSAI_AYURVEDA_AAHARA_DOCUMENT_ID = "india:national/fssai_ayurveda_aahara_regulations_2022"

NATIONAL_HEADING = re.compile(
    r"^\s*(?:\d+\s*\[\s*)?(\d+[A-Z]*)\.(?!\d)\s*(.+?)\s*$"
)
NATIONAL_BARE_HEADING = re.compile(
    r"^\s*(?:\d+\s*\[\s*)?(\d{1,3}[A-Z]*)\s+([A-Z]\S.*)$"
)
ARTICLE_HEADING = re.compile(r"^\s*article\s+(\d+[a-z]*(?:bis)?)\b\s*(?::|[-–—])?\s*(.*?)\s*$", re.I)
ARTICLE_ONLY = re.compile(r"^\s*article\s*$", re.I)
ARTICLE_NUMBER_ONLY = re.compile(r"^\s*(\d+[a-z]*(?:bis)?)\s*$", re.I)
CHAPTER_HEADING = re.compile(
    r"^\s*(?:\d+\s*\[\s*)?((?i:chapter|part)\s+(?:[IVXLCDMivxlcdm]+[A-Za-z]?|\d+[A-Za-z]?))\b\s*(.*)$"
)


def chapter_heading_match(text: str) -> re.Match[str] | None:
    """Reject sentence fragments that happen to start with ``Chapter IV``."""
    match = CHAPTER_HEADING.match(text)
    if match is None:
        return None
    remainder = match.group(2).strip()
    tail = text[match.start(1) + len(match.group(1)):].lstrip()
    if remainder and not tail.startswith((":", ".")) and not remainder[0].isupper():
        return None
    return match

SUBSECTION_MARKER = re.compile(r"^\s*\(([0-9]+[a-z]?|[a-z]|[ivxlcdm]+)\)\s*", re.I)
CONTENTS_MARKER = re.compile(
    r"\barrangement\s+of\s+(?:sections|rules|articles)\b|"
    r"\btable\s+of\s+(?:contents|articles|provisions)\b|"
    r"^\s*(?:contents|list\s+of\s+amending\s+acts)\s*$",
    re.I,
)
SCHEDULE_MARKER = re.compile(
    r"^\s*(?:(?:\d+\s*)?[\[(]\s*)?(?:THE\s+(?:(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|[IVXLCDM0-9]+)\s+)?SCHEDULE\b.*|SCHEDULE\s*[-\u2013]\s*[A-Z0-9]+\b.*|\u0905\u0928\u0941\u0938\u0942\u091A\u0940\s*[\u2018'\"(\[]?\s*[\u0915-\u0939]\s*[\u2019'\")\]]?.*)$"
)
NAMED_SCHEDULE_MARKER = re.compile(r"^\s*Schedule\s+[A-Z0-9]\s*$", re.I)
RULE_HEADING = re.compile(r"^\s*rule\s+\d+[a-z]*\s*\.", re.I)
# Body provisions use the title-case spelling in the extracted Patent Rules text.
# Keep this case-sensitive: lowercase ``rule 20.`` occurrences are references in
# the body, while RULE_HEADING remains case-insensitive for contents-page counts.
RULE_BODY_HEADING = re.compile(r"^\s*Rule\s+(\d+[A-Z]*)\s*\.\s*(.*?)\s*$")
PUBLICATION_ARTIFACT = re.compile(
    r"^\s*(?:printed\s+on\s+\d+%\s+recycled\s+paper|"
    r"printed\s+in\s+icao,\s*canada|july\s+2011)\s*$", re.I
)
BODY_START = re.compile(
    r"^\s*(?:an\s+act\s+to\b|the\s+(?:contracting\s+)?(?:states|parties)\b|"
    r"the\s+undersigned\b|desiring\s+to\b|conscious\s+of\b|have\s+(?:agreed|concluded)\b|"
    r"in\s+exercise\s+of\b|whereas\b|act\s+no\.\s*\d|the\s+.+?\bact(?:,|\s|$))",
    re.I,
)
LOGGER.setLevel(logging.INFO)


def load_extracted_documents(input_path: Path = INPUT_PATH) -> list[dict[str, Any]]:
    """Load the document list produced by Stage 1."""
    with input_path.open("r", encoding="utf-8-sig") as input_file:
        documents = json.load(input_file)
    if not isinstance(documents, list):
        raise ValueError("The extracted document JSON must contain a list")
    return documents


def normalize_page_text(text: str) -> list[str]:
    """Normalize line whitespace while preserving wording and line boundaries."""
    normalized: list[str] = []
    for line in text.replace("\r", "\n").split("\n"):
        line = re.sub(r"[\t\f\v ]+", " ", line).strip()
        if line:
            normalized.append(line)
    return normalized


def _is_body_start(text: str, jurisdiction: str = "") -> bool:
    lines = normalize_page_text(text)
    if any(BODY_START.match(line) for line in lines[:12]):
        return True
    if jurisdiction == "India":
        # Some Gazette PDFs start a Hindi statutory text with a numbered
        # provision, without an English "An Act" heading. Recognize a sparse
        # provision heading followed by nested clauses so later pages are not
        # mistaken for dense contents lists.
        heading_positions = [
            index for index, line in enumerate(lines[:8])
            if NATIONAL_HEADING.match(line)
        ]
        if len(heading_positions) == 1 and _count_heading_candidates(text, jurisdiction) <= 2:
            following = lines[heading_positions[0] + 1:12]
            nested_clauses = sum(
                bool(re.match(r"^\s*[([]\s*[\w\u0900-\u097f]", line))
                for line in following
            )
            if nested_clauses >= 2:
                return True
    if (
        any(line.casefold() == "notification" for line in lines[:8])
        and any(re.search(r"\bwhereas\b", line, re.I) for line in lines[:12])
    ):
        return True
    # A chapter heading plus only a small number of provision headings marks body text,
    # while contents pages list many section/article titles beneath chapter headings.
    has_chapter = any(chapter_heading_match(line) for line in lines[:8])
    return has_chapter and _count_heading_candidates(text, jurisdiction) <= 2


def _count_heading_candidates(text: str, jurisdiction: str) -> int:
    lines = normalize_page_text(text)
    if jurisdiction == "India":
        return sum(bool(NATIONAL_HEADING.match(line)) or bool(RULE_HEADING.match(line)) for line in lines)
    return sum(bool(ARTICLE_HEADING.match(line)) or bool(ARTICLE_ONLY.match(line)) for line in lines)


def detect_contents_page(text: str, jurisdiction: str) -> bool:
    """Identify explicit contents pages and dense provision-list pages."""
    lines = normalize_page_text(text)
    if any(CONTENTS_MARKER.search(line) for line in lines):
        return True
    heading_count = _count_heading_candidates(text, jurisdiction)
    long_lines = sum(len(line) > 180 for line in lines)
    return heading_count >= 7 and long_lines <= max(1, len(lines) // 12)




def _is_contents_continuation(text: str, jurisdiction: str) -> bool:
    """Recognize list-like pages that continue a contents list without its title."""
    if detect_contents_page(text, jurisdiction):
        return True
    lines = normalize_page_text(text)
    heading_count = _count_heading_candidates(text, jurisdiction)
    short_lines = sum(len(line) <= 160 for line in lines)
    return heading_count >= 4 and len(lines) <= 70 and short_lines / max(1, len(lines)) >= 0.8


def _find_contents_pages(documents: list[dict[str, Any]]) -> dict[str, set[int]]:
    """Mark contents pages and list continuations before substantive document text."""
    contents_by_document: dict[str, set[int]] = {}
    for document in documents:
        pages = document.get("pages", [])
        marked: set[int] = set()
        active_contents = False
        body_started = False
        explicit_pages = {
            int(page.get("page_number", 0))
            for page in pages
            if any(CONTENTS_MARKER.search(line) for line in normalize_page_text(page.get("text", "")))
        }
        first_explicit_page = min(explicit_pages) if explicit_pages else None
        for page in pages:
            page_number = int(page.get("page_number", 0))
            text = page.get("text", "")
            explicit = any(CONTENTS_MARKER.search(line) for line in normalize_page_text(text))
            if body_started:
                continue
            if explicit:
                marked.add(page_number)
                active_contents = True
                continue
            if _is_body_start(text, document.get("jurisdiction", "")):
                if first_explicit_page is not None and page_number < first_explicit_page:
                    continue
                body_started = True
                active_contents = False
                continue
            if active_contents:
                lines = normalize_page_text(text)
                has_final_schedule_entry = (
                    _count_heading_candidates(text, document.get("jurisdiction", "")) >= 1
                    and len(lines) <= 12
                    and any(line.upper().startswith("THE SCHEDULE") for line in lines)
                )
                if _is_contents_continuation(text, document.get("jurisdiction", "")) or has_final_schedule_entry:
                    marked.add(page_number)
                    continue
                # The list ended; later dense statutory pages are body text, not a contents continuation.
                body_started = True
                active_contents = False
                continue
            if page_number <= 6 and detect_contents_page(text, document.get("jurisdiction", "")):
                marked.add(page_number)
                active_contents = True
        contents_by_document[document["document_id"]] = marked
    return contents_by_document


def _looks_like_heading_title(text: str) -> bool:
    """Check whether a short following line is more like a title than prose."""
    words = text.split()
    if not words or len(words) > 16 or len(text) > 130:
        return False
    if re.match(r"^(?:the\s+)?(?:contracting\s+parties|parties|states|members)\b", text, re.I):
        return False
    if text.endswith((".", ";", ",")):
        return False
    return True


def detect_article_start(lines: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    """Detect a top-level international Article heading, including split forms."""
    text = lines[index]["text"]
    match = ARTICLE_HEADING.match(text)
    if match:
        number, remainder = match.groups()
        remainder = remainder.strip()
        if remainder and remainder[0].islower() and not text.startswith("ARTICLE "):
            return None
        title = remainder or None
        if title is None and index + 1 < len(lines) and _looks_like_heading_title(lines[index + 1]["text"]):
            title = lines[index + 1]["text"].strip(" :.-") or None
        return {"index": index, "type": "article", "number": number, "title": title}
    if ARTICLE_ONLY.match(text) and index + 1 < len(lines):
        number_match = ARTICLE_NUMBER_ONLY.match(lines[index + 1]["text"])
        if number_match:
            title = None
            if index + 2 < len(lines) and _looks_like_heading_title(lines[index + 2]["text"]):
                title = lines[index + 2]["text"].strip(" :.-") or None
            return {"index": index, "type": "article", "number": number_match.group(1), "title": title}
    return None


def detect_section_start(
    line: str, index: int, following_line: str | None = None
) -> dict[str, Any] | None:
    """Detect a likely national section heading at the beginning of a line."""
    match = NATIONAL_HEADING.match(line)
    if not match:
        return None
    number, remainder = match.groups()
    remainder = remainder.strip()
    # PDF extraction can wrap a provision title before its dash and subsection.
    # Include only a clear lowercase continuation ending at that dash.
    if following_line and not SUBSECTION_MARKER.match(remainder):
        dash = re.search(r"[\u2013\u2014]", following_line)
        if dash:
            continuation = following_line[:dash.start()].strip()
            if continuation and continuation[0].islower():
                remainder = f"{remainder} {continuation}"
    # Compiled-act editorial footnotes use numbered amendment notes, not section headings.
    if (
        re.match(r"^(?:(?:cls?\.|clauses?)\s+\([^)]+\)(?:\s+and\s+\([^)]+\))*\s+)?(?:subs(?:tituted)?\.?\s+by|ins(?:erted)?\.?\s+by|omitted\s+by|added\s+by)\b", remainder, re.I)
        or re.search(r"\b(?:omitted|substituted|inserted|added)\s+by\s+(?:act|s\.|the)\b", remainder, re.I)
        or re.match(r"^the\s+act\s+has\s+been\s+applied\b", remainder, re.I)
        or "ibid." in remainder.lower()
        or "vide notification" in remainder.lower()
        or re.search(r"\bw\.?\s*e\.?\s*f\.?\s*\d", remainder, re.I)
        or re.match(r"^\d{1,2}(?:st|nd|rd|th)\s+[A-Za-z]+[, ]+\d{4}\b", remainder, re.I)
    ):
        return None
    # A numbered subsection is child content, not a section title.
    if SUBSECTION_MARKER.match(remainder):
        title = None
    else:
        title = re.split(r"\s*[\u2013\u2014]\s*", remainder, maxsplit=1)[0].strip(" .:;") or None
    return {"index": index, "type": "section", "number": number, "title": title}


def _detect_bare_section_boundary(lines: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    """Accept a missing-period section heading only when the next numbered section confirms it."""
    match = NATIONAL_BARE_HEADING.match(lines[index]["text"])
    if not match:
        return None
    number, title = match.groups()
    number_match = re.fullmatch(r"(\d+)([A-Z]*)", number)
    if number_match is None:
        return None
    base, suffix = number_match.groups()
    if suffix:
        prefix, last = suffix[:-1], suffix[-1]
        expected_suffix = f"{prefix}{chr(ord(last) + 1)}" if last < "Z" else f"{prefix}A"
        expected_next = f"{base}{expected_suffix}"
    else:
        expected_next = str(int(base) + 1)
    for following in lines[index + 1:index + 4]:
        next_heading = NATIONAL_HEADING.match(following["text"])
        if next_heading:
            if next_heading.group(1).casefold() == expected_next.casefold():
                return {"index": index, "type": "section", "number": number, "title": title.strip(" .:;") or None}
            return None
        if len(following["text"]) > 180:
            return None
    return None


def detect_provision_start(
    lines: list[dict[str, Any]], index: int, jurisdiction: str
) -> dict[str, Any] | None:
    """Select the jurisdiction-appropriate provision detector."""
    if jurisdiction == "India":
        following_line = lines[index + 1]["text"] if index + 1 < len(lines) else None
        return (detect_rule_start(lines, index)
                or detect_section_start(lines[index]["text"], index, following_line)
                or _detect_bare_section_boundary(lines, index))
    return detect_article_start(lines, index)


def detect_rule_start(lines: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    """Recognize title-case top-level Rule headings and the known wrapped title form."""
    match = RULE_BODY_HEADING.match(lines[index]["text"])
    if match is None:
        return None
    number, title = match.groups()
    title = title.strip(" .:;")
    # In the extracted Patent Rules source, Rule 133's title wraps as
    # ``under sections`` / ``72 and 147``. Join only that structural form.
    if (re.search(r"\bunder\s+sections$", title, re.IGNORECASE)
            and index + 1 < len(lines)
            and re.fullmatch(r"\d+(?:\s+and\s+\d+)+\.?", lines[index + 1]["text"].strip())):
        title = f"{title} {lines[index + 1]['text'].strip().rstrip('.')}"
    return {"index": index, "type": "rule", "number": number, "title": title or None}


def _collect_lines(
    document: dict[str, Any], excluded_pages: set[int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Flatten page text into provenance-carrying lines and save contents separately."""
    lines: list[dict[str, Any]] = []
    contents_pages: list[dict[str, Any]] = []
    in_schedule = False
    break_before_next_line = False
    for page in document.get("pages", []):
        page_number = int(page.get("page_number", 0))
        page_text = page.get("text", "")
        page_lines = normalize_page_text(page_text)
        if in_schedule and _is_body_start(page_text, document.get("jurisdiction", "")):
            in_schedule = False
            break_before_next_line = True
        schedule_heading = False
        for index, line in enumerate(page_lines):
            if SCHEDULE_MARKER.match(line):
                schedule_heading = True
                break
            if NAMED_SCHEDULE_MARKER.match(line) and any(
                "[see " in following.lower()
                for following in page_lines[index + 1:index + 3]
            ):
                schedule_heading = True
                break
        if page_number not in excluded_pages and schedule_heading:
            in_schedule = True
        if page_number in excluded_pages or in_schedule:
            contents_pages.append({
                "document_id": document.get("document_id"),
                "document_name": document.get("document_name"),
                "filename": document.get("filename"),
                "jurisdiction": document.get("jurisdiction"),
                "source_path": document.get("source_path"),
                "page_type": "schedule" if in_schedule else "contents",
                "page_number": page_number,
                "text": page_text,
                "extraction_method": page.get("extraction_method"),
            })
            continue
        for text in normalize_page_text(page.get("text", "")):
            line_record = {
                "text": text,
                "page_number": page_number,
                "extraction_method": page.get("extraction_method", "none"),
            }
            if break_before_next_line:
                line_record["break_before"] = True
                break_before_next_line = False
            lines.append(line_record)
    return lines, contents_pages


def update_active_provision(
    lines: list[dict[str, Any]], jurisdiction: str
) -> tuple[list[dict[str, Any]], int]:
    """Group sequential text under provision headings while carrying chapter context."""
    groups: list[dict[str, Any]] = []
    warnings = 0
    active: dict[str, Any] | None = None
    pending: list[dict[str, Any]] = []
    chapter: str | None = None

    def flush_active() -> None:
        nonlocal active
        if active and active["lines"]:
            groups.append(active)
        active = None

    def flush_pending() -> None:
        if pending:
            groups.append({
                "type": None,
                "number": None,
                "title": None,
                "content_type": "general",
                "chapter_or_part": chapter,
                "lines": list(pending),
            })
            pending.clear()

    for index, record in enumerate(lines):
        if record.get("break_before"):
            flush_active()
            flush_pending()
        if (pending and int(record.get("page_number", 0))
                > int(pending[-1].get("page_number", 0)) + 1):
            # A skipped page interval commonly contains contents pages. Keep
            # preceding front matter separate from the later provision body.
            flush_pending()
        chapter_match = chapter_heading_match(record["text"])
        if chapter_match:
            flush_active()
            flush_pending()
            chapter = " ".join(part for part in chapter_match.groups() if part).strip()
            if not chapter_match.group(2).strip() and index + 1 < len(lines):
                continuation = lines[index + 1]["text"].strip()
                if (continuation and len(continuation) <= 180
                        and continuation.upper() == continuation
                        and lines[index + 1].get("page_number") == record.get("page_number")
                        and not chapter_heading_match(continuation)
                        and not detect_provision_start(lines, index + 1, jurisdiction)):
                    chapter = f"{chapter} {continuation}".strip()
                    lines[index + 1]["chapter_context_continuation"] = True
            record["chapter_context"] = True
            pending.append(record)
            continue
        if PUBLICATION_ARTIFACT.match(record["text"]):
            flush_active()
            pending.append(record)
            continue

        candidate = detect_provision_start(lines, index, jurisdiction)
        if candidate:
            # Reject obvious prose references which happen to begin a line with a number.
            if candidate["type"] == "section" and candidate["title"]:
                title_text = candidate["title"].lower()
                if re.match(r"^(?:of\b|to\b|in accordance\b|shall\b|may\b|means\b)", title_text):
                    candidate = None
            if (candidate and active and candidate.get("type") == "section"
                    and active.get("type") == "section"
                    and str(candidate.get("number")).casefold() == str(active.get("number")).casefold()
                    and active["lines"]
                    and active["lines"][-1].get("page_number") == record.get("page_number")):
                # A repeated same-page section number is an editorial note or line repeat,
                # not a second top-level section boundary.
                candidate = None
            if candidate:
                flush_active()
                chapter_lines = (
                    list(pending)
                    if pending
                    and all(line.get("chapter_context") or line.get("chapter_context_continuation")
                            for line in pending)
                    and all(line.get("page_number") == record.get("page_number") for line in pending)
                    else []
                )
                if chapter_lines:
                    pending.clear()
                else:
                    flush_pending()
                active = {
                    **candidate,
                    "content_type": "provision",
                    "chapter_or_part": chapter,
                    "lines": [*chapter_lines, record],
                }
                if candidate.get("title") is None and candidate["type"] is None:
                    warnings += 1
            elif active is not None:
                active["lines"].append(record)
            else:
                pending.append(record)
        elif active is not None:
            active["lines"].append(record)
        else:
            pending.append(record)

    flush_active()
    flush_pending()
    return groups, warnings


def _line_text(lines: list[dict[str, Any]]) -> str:
    """Join normalized source lines without changing their wording."""
    return "\n".join(line["text"] for line in lines).strip()


def _split_oversized_lines(lines: list[dict[str, Any]], max_chars: int) -> list[list[dict[str, Any]]]:
    """Split a large block on line or word boundaries without overlap."""
    result: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_size = 0
    for record in lines:
        text = record["text"]
        if len(text) > max_chars:
            if current:
                result.append(current)
                current, current_size = [], 0
            words = text.split()
            fragment = ""
            for word in words:
                if fragment and len(fragment) + len(word) + 1 > max_chars:
                    result.append([{**record, "text": fragment}])
                    fragment = word
                else:
                    fragment = f"{fragment} {word}".strip()
            if fragment:
                current = [{**record, "text": fragment}]
                current_size = len(fragment)
            continue
        addition = len(text) + (1 if current else 0)
        if current and current_size + addition > max_chars:
            result.append(current)
            current, current_size = [], 0
        current.append(record)
        current_size += len(text) + (1 if len(current) > 1 else 0)
    if current:
        result.append(current)
    return result


def split_large_provision(
    provision: dict[str, Any], max_chars: int = MAX_CHUNK_CHARS
) -> list[list[dict[str, Any]]]:
    """Pack complete child-subsection blocks before splitting oversized provisions."""
    lines = provision["lines"]
    units: list[list[dict[str, Any]]] = []
    current_unit: list[dict[str, Any]] = []
    for record in lines:
        is_child = bool(SUBSECTION_MARKER.match(record["text"]))
        if is_child and current_unit:
            units.append(current_unit)
            current_unit = []
        current_unit.append(record)
    if current_unit:
        units.append(current_unit)

    packed: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_size = 0
    for unit in units:
        unit_size = len(_line_text(unit))
        if unit_size > max_chars:
            if current:
                packed.append(current)
                current, current_size = [], 0
            packed.extend(_split_oversized_lines(unit, max_chars))
        elif current and current_size + unit_size + 1 > max_chars:
            packed.append(current)
            current, current_size = list(unit), unit_size
        else:
            current.extend(unit)
            current_size += unit_size + (1 if current_size else 0)
    if current:
        packed.append(current)
    return packed or [lines]


def _chunk_metadata(group: dict[str, Any], chunk_lines: list[dict[str, Any]]) -> dict[str, Any]:
    pages = list(dict.fromkeys(line["page_number"] for line in chunk_lines))
    methods = list(dict.fromkeys(line["extraction_method"] for line in chunk_lines if line.get("extraction_method")))
    child_markers = [
        f"({match.group(1)})" for line in chunk_lines
        if (match := SUBSECTION_MARKER.match(line["text"]))
    ]
    subsection_path = [child_markers[0]] if len(child_markers) == 1 else []
    return {
        "document_id": None,
        "document_name": None,
        "filename": None,
        "jurisdiction": None,
        "source_path": None,
        "provision_type": group.get("type"),
        "content_type": group.get("content_type", "provision" if group.get("type") else "general"),
        "provision_number": group.get("number"),
        "provision_title": group.get("title"),
        "chapter_or_part": group.get("chapter_or_part"),
        "subsection_path": subsection_path,
        "text": _line_text(chunk_lines),
        "page_start": min(pages) if pages else None,
        "page_end": max(pages) if pages else None,
        "source_pages": pages,
        "extraction_methods": methods,
    }


def build_provision_chunks(
    document: dict[str, Any], groups: list[dict[str, Any]], max_chars: int = MAX_CHUNK_CHARS
) -> tuple[list[dict[str, Any]], int, int]:
    """Create fully attributed chunks and count multi-page and split provisions."""
    chunks: list[dict[str, Any]] = []
    multipage = 0
    split_provisions = 0
    chunk_index = 0
    for group in groups:
        if not group["lines"]:
            continue
        source_pages = {line["page_number"] for line in group["lines"]}
        if group.get("type") and len(source_pages) > 1:
            multipage += 1
        pieces = split_large_provision(group, max_chars)
        if group.get("type") and len(pieces) > 1:
            split_provisions += 1
        for provision_chunk_index, piece in enumerate(pieces):
            metadata = _chunk_metadata(group, piece)
            metadata.update({
                "chunk_id": f"{document['document_id']}#chunk-{chunk_index:04d}",
                "document_id": document.get("document_id"),
                "document_name": document.get("document_name"),
                "filename": document.get("filename"),
                "jurisdiction": document.get("jurisdiction"),
                "source_path": document.get("source_path"),
                "chunk_index": chunk_index,
                "provision_chunk_index": provision_chunk_index,
            })
            chunks.append(metadata)
            chunk_index += 1
    return chunks, multipage, split_provisions


def process_documents(documents: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build provision chunks and preserved contents-page records for all documents."""
    all_chunks: list[dict[str, Any]] = []
    all_contents: list[dict[str, Any]] = []
    zero_provision_documents: list[str] = []
    warnings: list[str] = []
    multipage_count = 0
    split_count = 0
    documents_processed = 0
    for document in documents:
        try:
            contents_by_document = _find_contents_pages([document])
            contents_numbers = contents_by_document.get(document["document_id"], set())
            lines, contents = _collect_lines(document, contents_numbers)
            groups, candidate_warnings = update_active_provision(lines, document.get("jurisdiction", ""))
            for content_page in contents:
                page_number = int(content_page.get("page_number", 0))
                page_lines = [
                    {"text": text, "page_number": page_number,
                     "extraction_method": content_page.get("extraction_method") or "none"}
                    for text in normalize_page_text(content_page.get("text", ""))
                ]
                if page_lines:
                    groups.append({
                        "type": None, "number": None, "title": None,
                        "content_type": content_page.get("page_type", "contents"),
                        "chapter_or_part": None, "lines": page_lines,
                    })
            provision_count = sum(group.get("type") is not None for group in groups)
            if provision_count == 0:
                zero_provision_documents.append(document.get("filename", document["document_id"]))
            chunks, multipage, split = build_provision_chunks(document, groups)
            if document.get("document_id") == FSSAI_AYURVEDA_AAHARA_DOCUMENT_ID:
                # These recognized numbered body provisions are Regulations,
                # while contents and schedule pages are emitted separately.
                for chunk in chunks:
                    if (chunk.get("content_type") == "provision"
                            and chunk.get("provision_type") == "section"):
                        chunk["provision_type"] = "regulation"
            all_chunks.extend(chunks)
            all_contents.extend(contents)
            multipage_count += multipage
            split_count += split
            documents_processed += 1
            if candidate_warnings:
                warnings.append(
                    f"{document.get('filename')}: {candidate_warnings} provision heading(s) had no reliable title"
                )
            if provision_count == 0:
                warnings.append(f"{document.get('filename')}: no top-level provisions detected; text retained as general chunks")
        except Exception as error:
            warnings.append(f"{document.get('filename', '<unknown>')}: {type(error).__name__}: {error}")
            LOGGER.exception("Could not chunk document %s", document.get("filename", "<unknown>"))
    output = {"chunks": all_chunks, "contents_pages": all_contents}
    stats = {
        "documents_processed": documents_processed,
        "total_chunks": len(all_chunks),
        "chunks_by_jurisdiction": dict(Counter(chunk["jurisdiction"] for chunk in all_chunks)),
        "chunks_by_provision_type": dict(Counter(str(chunk["provision_type"]) for chunk in all_chunks)),
        "chunks_by_content_type": dict(Counter(chunk.get("content_type", "unknown") for chunk in all_chunks)),
        "documents_with_zero_provisions": zero_provision_documents,
        "multi_page_provisions": multipage_count,
        "provisions_split": split_count,
        "contents_pages": len(all_contents),
        "warnings": warnings,
    }
    return output, stats


def write_chunks(chunks_output: dict[str, Any], output_path: Path = OUTPUT_PATH) -> None:
    """Write chunks and separately preserved contents pages to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(chunks_output, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def _print_summary(stats: dict[str, Any], output_path: Path) -> None:
    """Print chunk totals and any parsing warnings."""
    print("\nChunking summary")
    print(f"Documents processed: {stats['documents_processed']}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Chunks by jurisdiction: {stats['chunks_by_jurisdiction']}")
    print(f"Chunks by provision type: {stats['chunks_by_provision_type']}")
    print(f"Chunks by content type: {stats['chunks_by_content_type']}")
    print(f"Documents with zero detected provisions: {len(stats['documents_with_zero_provisions'])} {stats['documents_with_zero_provisions']}")
    print(f"Multi-page provisions: {stats['multi_page_provisions']}")
    print(f"Provisions split into multiple chunks: {stats['provisions_split']}")
    print(f"Contents pages preserved separately: {stats['contents_pages']}")
    print(f"Parsing warnings/errors: {len(stats['warnings'])}")
    for warning in stats["warnings"]:
        print(f"  - {warning}")
    print(f"Output JSON: {output_path.relative_to(PROJECT_ROOT).as_posix()}")


def main() -> None:
    """Run Stage 2 chunking and print the resulting corpus summary."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    documents = load_extracted_documents()
    chunks_output, stats = process_documents(documents)
    write_chunks(chunks_output)
    _print_summary(stats, OUTPUT_PATH)


if __name__ == "__main__":
    main()
