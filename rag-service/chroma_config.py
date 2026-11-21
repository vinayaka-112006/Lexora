"""Shared Chroma persistence-path configuration."""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHROMA_PATH = PROJECT_ROOT / "rag-service" / "chroma_db"
CHROMA_PATH_ENV = "CHROMA_PATH"
DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "rag-service" / "data" / "chunks.json"
CHUNKS_PATH_ENV = "CHUNKS_PATH"


def resolve_chroma_path(configured_path: str | Path | None = None) -> Path:
    """Resolve CHROMA_PATH relative to the project root, preserving the legacy default."""
    value = os.getenv(CHROMA_PATH_ENV) if configured_path is None else configured_path
    if value is None or not str(value).strip():
        return DEFAULT_CHROMA_PATH
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def resolve_chunks_path(configured_path: str | Path | None = None) -> Path:
    """Resolve CHUNKS_PATH relative to the project root, preserving the canonical default."""
    value = os.getenv(CHUNKS_PATH_ENV) if configured_path is None else configured_path
    if value is None or not str(value).strip():
        return DEFAULT_CHUNKS_PATH
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def resolve_index_paths(
    chroma_path: str | Path | None = None,
    chunks_path: str | Path | None = None,
) -> tuple[Path, Path, bool]:
    """Resolve a matched index/chunk-map pair, rejecting partial configuration."""
    chroma_value = os.getenv(CHROMA_PATH_ENV) if chroma_path is None else chroma_path
    chunks_value = os.getenv(CHUNKS_PATH_ENV) if chunks_path is None else chunks_path
    chroma_configured = chroma_value is not None and bool(str(chroma_value).strip())
    chunks_configured = chunks_value is not None and bool(str(chunks_value).strip())
    if chroma_configured != chunks_configured:
        raise ValueError("CHROMA_PATH and CHUNKS_PATH must be configured together as a matched pair")
    return (
        resolve_chroma_path(chroma_value if chroma_configured else None),
        resolve_chunks_path(chunks_value if chunks_configured else None),
        chroma_configured,
    )



# Summary: ChromaDB Configuration File
# This file is responsible for managing and resolving the storage paths of IP-SAKTI's ChromaDB vector database and its corresponding chunks.json file.

# It ensures that the application knows exactly where to find these resources, regardless of which directory you run the application from.
# Main functions
# Function	Purpose
# resolve_chroma_path()	Finds the ChromaDB database directory.
# resolve_chunks_path()	Finds the chunks.json file.
# resolve_index_paths()	Resolves both paths and checks that custom paths are configured together.

# Why is this file needed in IP-SAKTI?
# Your RAG system needs two important resources:
# 1. ChromaDB: Stores vector embeddings and associated metadata of legal document chunks. It enables semantic search.
# 2. chunks.json: Stores the canonical chunk data, including legal text and metadata, used by other parts of the RAG pipeline.
# This configuration file helps ensure that both resources are loaded from the correct locations.
# Important responsibilities
# - Reads paths from environment variables.
# - Supports custom paths passed as function arguments.
# - Converts relative paths into absolute paths using PROJECT_ROOT.
# - Uses default paths when no custom configuration exists.
# - Prevents partial custom configuration that could cause the index and chunk mapping to become mismatched.