"""Embed Stage 2 legal chunks and store them in persistent ChromaDB."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_SERVICE_ROOT = PROJECT_ROOT / "rag-service"
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))
from chroma_config import resolve_index_paths

PERSIST_PATH, INPUT_PATH, _PATHS_CONFIGURED = resolve_index_paths()
COLLECTION_NAME = "ip_sakti_legal"
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 64
METADATA_FIELDS = (
    "document_id",
    "document_name",
    "filename",
    "jurisdiction",
    "provision_type",
    "provision_number",
    "provision_title",
    "chapter_or_part",
    "subsection_path",
    "page_start",
    "page_end",
    "source_pages",
    "extraction_methods",
    "chunk_index",
    "provision_chunk_index",
    "content_type",
)
LOGGER = logging.getLogger("build_index")


def load_chunks(input_path: Path = INPUT_PATH) -> list[dict[str, Any]]:
    """Load and validate the source chunks without changing their text."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Chunks JSON was not found: {input_path}")
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Malformed chunks JSON at {input_path}: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("chunks"), list):
        raise ValueError("chunks.json must contain an object with a 'chunks' list")
    chunks = payload["chunks"]
    if not chunks:
        raise ValueError("chunks.json contains no chunks")
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk at position {index} is not an object")
        if not isinstance(chunk.get("text"), str) or not chunk["text"].strip():
            raise ValueError(f"Chunk at position {index} has no usable text")
    return chunks


def stable_chunk_id(chunk: dict[str, Any]) -> str:
    """Derive a repeatable Chroma ID from the document and chunk identity."""
    document_id = str(chunk.get("document_id") or "")
    chunk_index = chunk.get("chunk_index")
    if not document_id or chunk_index is None:
        raise ValueError("Every chunk must have document_id and chunk_index for a stable ID")
    identity = f"{document_id}#chunk-{chunk_index}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _metadata_value(value: Any) -> str | int | float | bool:
    """Convert metadata to Chroma-safe scalar values, preserving arrays as JSON."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def chunk_metadata(chunk: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Build Chroma-compatible metadata while retaining every Stage 2 field."""
    return {key: _metadata_value(chunk.get(key)) for key in METADATA_FIELDS}


def _open_collection(chromadb: Any, persist_path: Path, model_name: str) -> Any:
    """Open the corpus collection, rebuilding it if it uses a different model."""
    client = chromadb.PersistentClient(path=str(persist_path))
    existing_names = {
        item.name if hasattr(item, "name") else str(item)
        for item in client.list_collections()
    }
    if COLLECTION_NAME in existing_names:
        collection = client.get_collection(name=COLLECTION_NAME)
        if (collection.metadata or {}).get("embedding_model") != model_name:
            LOGGER.warning(
                "Rebuilding %s because its embedding model differs from %s",
                COLLECTION_NAME,
                model_name,
            )
            client.delete_collection(name=COLLECTION_NAME)
        else:
            return client, collection
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "embedding_model": model_name},
    )
    return client, collection


def _remove_stale_records(collection: Any, expected_ids: set[str]) -> None:
    """Remove records left over from a previous, larger source chunk set."""
    existing_ids = collection.get(include=[]).get("ids", [])
    stale_ids = [record_id for record_id in existing_ids if record_id not in expected_ids]
    for start in range(0, len(stale_ids), 500):
        collection.delete(ids=stale_ids[start : start + 500])


def index_chunks(
    chunks: list[dict[str, Any]],
    model_name: str,
    batch_size: int,
    persist_path: Path = PERSIST_PATH,
) -> tuple[Any, int]:
    """Embed chunks in batches and upsert them under deterministic IDs."""
    if batch_size <= 0:
        raise ValueError("EMBEDDING_BATCH_SIZE must be a positive integer")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError(
            "sentence-transformers is required; install rag-service/requirements.txt"
        ) from error
    try:
        import chromadb
    except ImportError as error:
        raise RuntimeError("chromadb is required; install rag-service/requirements.txt") from error

    try:
        model = SentenceTransformer(model_name)
    except Exception as error:
        raise RuntimeError(f"Could not load embedding model {model_name!r}: {error}") from error
    try:
        persist_path.mkdir(parents=True, exist_ok=True)
        client, collection = _open_collection(chromadb, persist_path, model_name)
    except Exception as error:
        raise RuntimeError(f"Could not initialize ChromaDB at {persist_path}: {error}") from error

    identifiers = [stable_chunk_id(chunk) for chunk in chunks]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate document_id/chunk_index identities found in chunks.json")
    _remove_stale_records(collection, set(identifiers))

    embedded = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        try:
            outgoing_texts = [chunk["text"].replace("\x00", "") for chunk in batch]
            vectors = model.encode(
                outgoing_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            collection.upsert(
                ids=identifiers[start : start + len(batch)],
                embeddings=vectors.tolist(),
                documents=outgoing_texts,
                metadatas=[chunk_metadata(chunk) for chunk in batch],
            )
        except Exception as error:
            raise RuntimeError(f"Failed to embed or store chunk batch beginning at {start}: {error}") from error
        embedded += len(batch)
        print(f"Indexed {embedded}/{len(chunks)} chunks", end="\r", flush=True)
    print()

    record_count = collection.count()
    if embedded != len(chunks):
        raise RuntimeError(f"Generated {embedded} embeddings for {len(chunks)} chunks")
    if record_count != len(chunks):
        raise RuntimeError(
            f"Chroma contains {record_count} records; expected exactly {len(chunks)}"
        )
    return (model, collection), embedded


def run_sanity_queries(model: Any, collection: Any, result_count: int = 5) -> None:
    """Print a small semantic-search smoke check over the indexed legal chunks."""
    queries = (
        "Which things are not inventions under Section 3 of Indian patent law?",
        "What is the purpose of the Nagoya Protocol?",
        "What is the meaning of trade mark under the Trade Marks Act?",
    )
    for query in queries:
        print(f"\nQuery: {query}")
        query_vector = model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )[0]
        result = collection.query(
            query_embeddings=[query_vector.tolist()],
            n_results=min(result_count, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        if not ids:
            raise RuntimeError(f"Sanity query returned no results: {query}")
        for document, metadata, distance in zip(documents, metadatas, distances):
            print(
                "  - "
                f"document={metadata.get('document_name') or metadata.get('filename')}; "
                f"jurisdiction={metadata.get('jurisdiction')}; "
                f"provision_type={metadata.get('provision_type')}; "
                f"provision_number={metadata.get('provision_number')}; "
                f"title={metadata.get('provision_title')}; "
                f"pages={metadata.get('page_start')}-{metadata.get('page_end')}; "
                f"distance={distance:.4f}; text={document[:150]!r}"
            )


def main() -> None:
    """Run dense indexing, validate the persisted collection, and smoke-test search."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL).strip()
    try:
        batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
    except ValueError as error:
        raise SystemExit("EMBEDDING_BATCH_SIZE must be an integer") from error
    if not model_name:
        raise SystemExit("EMBEDDING_MODEL must not be empty")

    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks from {INPUT_PATH}")
    (model, collection), embeddings_generated = index_chunks(chunks, model_name, batch_size)
    jurisdiction_counts = Counter(str(chunk.get("jurisdiction") or "") for chunk in chunks)
    content_type_counts = Counter(str(chunk.get("content_type") or "") for chunk in chunks)
    print("\nDense indexing summary")
    print(f"Chunks loaded: {len(chunks)}")
    print(f"Embeddings generated: {embeddings_generated}")
    print(f"Chroma records: {collection.count()}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Persistence path: {PERSIST_PATH}")
    print(f"Embedding model: {model_name}")
    print(f"Batch size: {batch_size}")
    print(f"Chunks by jurisdiction: {dict(jurisdiction_counts)}")
    print(f"Chunks by content_type: {dict(content_type_counts)}")
    run_sanity_queries(model, collection)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Indexing failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error



# 12. How your actual 1,349 chunks are indexed
# Let's put everything together.
# Your project's indexing configuration
# Input chunks
# 1,349

# Embedding dimensions
# 384

# Batch size
# 64

# Total batches
# 22



# Jurisdiction distribution
# India
# 976



# International
# 373




# Expected ChromaDB records1,349

# These are your previously reported project figures, not a fresh execution of the indexing script.

# 13. Important distinction: ChromaDB vs BM25
# This is something you should understand well for the presentation.

# buildIndex.py creates the dense vector index.

# It does not create the BM25 keyword index in this file.

# Your retrieval architecture later combines:
# Retrieval method	What it does
# Dense retrieval	Finds semantically similar chunks using embeddings and ChromaDB
# BM25 retrieval	Finds chunks using keyword matching
# RRF	Combines the two ranked result lists

# For example, consider:

# User query:
# Can traditional Ayurvedic knowledge be patented?

# Dense retrieval may identify passages about traditional knowledge and patentability, even when the exact wording differs.

# BM25 may identify passages containing exact terms such as "traditional knowledge" and "patentability".

# Your later hybrid retrieval stage combines both results using Reciprocal Rank Fusion.

# So remember:

# This file builds the dense index, not the entire hybrid retrieval system.

# 14. What to tell the judges
# You can explain this file like this:
# "After legal documents are extracted and divided into provision-aware chunks, we use the Sentence Transformers all-MiniLM-L6-v2 model to convert each chunk into a 384-dimensional embedding. We store the embeddings, original text, and legal metadata in a persistent ChromaDB collection using cosine distance. We use deterministic chunk IDs, batch processing, stale-record cleanup, and record-count validation to make indexing reproducible and reliable. This creates the dense retrieval component, which is later combined with BM25 keyword retrieval."

# 15. A few implementation details worth remembering
# - If the embedding model changes, the existing collection is rebuilt because its vectors are not compatible with the new model.
# - If the chunk file changes, stale records are removed and existing IDs are updated through upsert().
# - The sanity queries are smoke tests, not a formal retrieval evaluation.
# - Metadata arrays are converted into JSON strings before storage.
# - The collection uses cosine distance, and embeddings are normalized before storage.

# Quick knowledge check
# 1. What does all-MiniLM-L6-v2 do in this file?

# Extracts PDF text

# Converts legal text into numerical embeddings

# Performs BM25 keyword search




# 2. Why does the code generate stable chunk IDs?

# To avoid duplicate records and support repeatable updates

# To increase embedding dimensions

# To identify the user's jurisdiction




# 3. Does buildIndex.py build the BM25 index?

# Yes, it builds both indexes

# No, it builds the dense ChromaDB index

# No, it only extracts PDF text



# Check answers
# We've now completed all three files in data_prep/.

# Next, we should inspect the data/ folder to understand the generated artifacts (extracted_documents.json and chunks.json) and how they relate to the actual ChromaDB collection.