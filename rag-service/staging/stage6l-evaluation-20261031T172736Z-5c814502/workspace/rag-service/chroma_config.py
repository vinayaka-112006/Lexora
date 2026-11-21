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
