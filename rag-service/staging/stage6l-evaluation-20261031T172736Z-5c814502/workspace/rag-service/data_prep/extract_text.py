"""Extract legal PDF text with OCR fallback for scanned image pages."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pypdfium2 as pdfium
from pypdf import PdfReader
from rapidocr import RapidOCR

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = PROJECT_ROOT / "corpus"
OUTPUT_PATH = PROJECT_ROOT / "rag-service" / "data" / "extracted_documents.json"
JURISDICTIONS = {"national": "India", "international": "International"}
# The filename reflects a local update label; the PDF title page identifies this source
# as The Patents Act, 1970. Keep the verified source title stable during re-extraction.
DOCUMENT_NAME_OVERRIDES = {
    "national/patent_act_2024.pdf": "The Patents Act, 1970",
}
HEADING_PATTERN = re.compile(
    r"^\s*((?:section|article|chapter|part|rule|regulation|schedule)\s+"
    r"[\w.-]+(?:\s*[:.)-]\s*|\s+).{0,180}|"
    r"(?:section|article|chapter|part|rule|regulation|schedule)\s+[\w.-]+)\s*$",
    re.IGNORECASE,
)
LOGGER = logging.getLogger("extract_text")


def discover_pdfs() -> list[tuple[Path, str]]:
    """Find corpus PDFs and pair each with its directory-derived jurisdiction."""
    discovered: list[tuple[Path, str]] = []
    for folder, jurisdiction in JURISDICTIONS.items():
        root = CORPUS_ROOT / folder
        if not root.is_dir():
            LOGGER.warning("Corpus directory is missing: %s", root)
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() == ".pdf":
                discovered.append((path, jurisdiction))
    return discovered


def readable_name(filename: str) -> str:
    """Turn a filename stem into a readable display name."""
    return re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", Path(filename).stem)).strip().title()


def document_display_name(pdf_path: Path) -> str:
    """Use a verified source title when available, otherwise derive a readable filename."""
    try:
        source_key = pdf_path.resolve().relative_to(CORPUS_ROOT.resolve()).as_posix()
    except ValueError:
        source_key = pdf_path.name
    return DOCUMENT_NAME_OVERRIDES.get(source_key, readable_name(pdf_path.name))


def page_contains_images(page: Any) -> bool:
    """Return whether pypdf identifies image objects on the PDF page."""
    try:
        return bool(page.images)
    except Exception as error:
        LOGGER.warning("Could not inspect page images: %s", error)
        raise


def ocr_page(pdf_document: Any, page_index: int, engine: RapidOCR) -> str:
    """Render one PDF page and return OCR text in the engine's reading order."""
    bitmap = pdf_document[page_index].render(scale=3.0)
    image = np.asarray(bitmap.to_pil().convert("RGB"))
    result = engine(image)
    texts = getattr(result, "txts", None) or []
    return "\n".join(text.strip() for text in texts if text and text.strip())


def extract_pdf(
    pdf_path: Path, jurisdiction: str, ocr_engine: RapidOCR
) -> tuple[dict[str, Any], int, int, int, list[str]]:
    """Extract a PDF page by page, applying OCR only to image pages without text."""
    relative_path = pdf_path.relative_to(PROJECT_ROOT).as_posix()
    document: dict[str, Any] = {
        "document_id": f"{jurisdiction.lower()}:{pdf_path.relative_to(CORPUS_ROOT).with_suffix('').as_posix()}",
        "document_name": document_display_name(pdf_path),
        "filename": pdf_path.name,
        "jurisdiction": jurisdiction,
        "source_path": relative_path,
        "pages": [],
        "extraction_errors": [],
    }
    reader = PdfReader(str(pdf_path))
    pdf_document = None
    pypdf_count = 0
    ocr_count = 0
    no_text_count = 0
    ocr_errors: list[str] = []
    for page_index, page in enumerate(reader.pages):
        page_number = page_index + 1
        page_record: dict[str, Any] = {"page_number": page_number, "text": ""}
        try:
            page_text = page.extract_text() or ""
            if page_text.strip():
                page_record["text"] = page_text
                page_record["extraction_method"] = "pypdf"
                pypdf_count += 1
            elif page_contains_images(page):
                page_record["extraction_method"] = "ocr"
                try:
                    if pdf_document is None:
                        pdf_document = pdfium.PdfDocument(str(pdf_path))
                    page_text = ocr_page(pdf_document, page_index, ocr_engine)
                    page_record["text"] = page_text
                    if page_text.strip():
                        ocr_count += 1
                        page_record["detected_headings"] = [
                            line.strip() for line in page_text.splitlines() if HEADING_PATTERN.match(line)
                        ]
                        if not page_record["detected_headings"]:
                            page_record.pop("detected_headings")
                    else:
                        message = f"Page {page_number}: OCR returned no text for an image page"
                        page_record["extraction_error"] = message
                        document["extraction_errors"].append(message)
                        ocr_errors.append(message)
                        LOGGER.warning("%s — %s", pdf_path, message)
                except Exception as error:
                    message = f"Page {page_number}: OCR failed: {type(error).__name__}: {error}"
                    page_record["extraction_error"] = message
                    document["extraction_errors"].append(message)
                    ocr_errors.append(message)
                    LOGGER.warning("%s — %s", pdf_path, message)
            else:
                page_record["extraction_method"] = "none"
                no_text_count += 1
        except Exception as error:
            message = f"Page {page_number}: extraction failed: {type(error).__name__}: {error}"
            page_record["extraction_method"] = "none"
            page_record["extraction_error"] = message
            document["extraction_errors"].append(message)
            LOGGER.warning("%s — %s", pdf_path, message)
        if page_record.get("extraction_method") == "pypdf":
            headings = [line.strip() for line in page_record["text"].splitlines() if HEADING_PATTERN.match(line)]
            if headings:
                page_record["detected_headings"] = headings
        document["pages"].append(page_record)
    if pdf_document is not None:
        pdf_document.close()
    return document, pypdf_count, ocr_count, no_text_count, ocr_errors


def process_corpus() -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Process PDFs independently and aggregate document, page, and OCR counts."""
    pdfs = discover_pdfs()
    documents: list[dict[str, Any]] = []
    failed = 0
    totals = {"pages_processed": 0, "pages_pypdf": 0, "pages_ocr": 0, "pages_none": 0, "ocr_failures": 0}
    ocr_engine: RapidOCR | None = None
    for pdf_path, jurisdiction in pdfs:
        try:
            if ocr_engine is None:
                ocr_engine = RapidOCR()
            document, pypdf_count, ocr_count, no_text_count, ocr_errors = extract_pdf(
                pdf_path, jurisdiction, ocr_engine
            )
            documents.append(document)
            totals["pages_processed"] += len(document["pages"])
            totals["pages_pypdf"] += pypdf_count
            totals["pages_ocr"] += ocr_count
            totals["pages_none"] += no_text_count
            totals["ocr_failures"] += len(ocr_errors)
            if not document["pages"]:
                failed += 1
                LOGGER.warning("No pages were readable in %s", pdf_path)
            if document["extraction_errors"]:
                LOGGER.warning("Page extraction errors in %s: %d", pdf_path, len(document["extraction_errors"]))
        except Exception as error:
            failed += 1
            LOGGER.exception("Failed to process %s: %s", pdf_path, error)
    stats = {"discovered": len(pdfs), "successfully_processed": len(pdfs) - failed, "failed": failed, **totals}
    return documents, stats


def save_results(documents: list[dict[str, Any]], output_path: Path = OUTPUT_PATH) -> None:
    """Write extracted documents as UTF-8 JSON, creating the output folder."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(documents, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def main() -> None:
    """Run corpus extraction and print a concise processing summary."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    documents, stats = process_corpus()
    try:
        save_results(documents)
    except Exception:
        LOGGER.exception("Could not save extracted documents to %s", OUTPUT_PATH)
        raise
    print("\nExtraction summary")
    print(f"PDFs discovered: {stats['discovered']}")
    print(f"Successfully processed: {stats['successfully_processed']}")
    print(f"Failed PDFs: {stats['failed']}")
    print(f"Total pages: {stats['pages_processed']}")
    print(f"Pages extracted with pypdf: {stats['pages_pypdf']}")
    print(f"Pages extracted with OCR: {stats['pages_ocr']}")
    print(f"Pages with no text/content: {stats['pages_none']}")
    print(f"OCR failures: {stats['ocr_failures']}")
    print(f"Output JSON: {OUTPUT_PATH.relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
