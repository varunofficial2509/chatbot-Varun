"""Document ingestion: extract -> normalize -> chunk -> embed -> store.

Owns everything under data/knowledge/: saving newly uploaded files, listing
what's currently there, and (re)building the vector store + profile from
whatever files are on disk. Supports PDF, Markdown, and JSON.
"""

import hashlib
import json
import logging
import re
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import config as settings
from app.rag.vectorstore import get_vectorstore

logger = logging.getLogger("recruiter_bot.ingestion")

REQUIRED_PROFILE_FIELDS = ["name", "headline", "skills"]


class IngestionError(ValueError):
    """Raised when uploaded content fails validation."""


class UnsupportedFileType(IngestionError):
    """Raised when a file extension isn't one of the supported knowledge types."""


# --- extraction -------------------------------------------------------------


def extract_pdf_text(path: Path) -> str:
    with fitz.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)


def extract_markdown_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix == ".md":
        return extract_markdown_text(path)
    raise UnsupportedFileType(f"Unsupported knowledge file type: {suffix}")


# --- normalize / validate / chunk -------------------------------------------


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def validate_profile(profile: dict) -> None:
    if not isinstance(profile, dict):
        raise IngestionError("Profile JSON must be an object.")
    missing = [f for f in REQUIRED_PROFILE_FIELDS if f not in profile]
    if missing:
        raise IngestionError(f"Profile JSON is missing required fields: {', '.join(missing)}")


def parse_profile_json(raw_bytes: bytes) -> dict:
    try:
        profile = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise IngestionError(f"Invalid JSON profile: {exc}") from exc
    validate_profile(profile)
    return profile


def content_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c for c in splitter.split_text(text) if c.strip()]


# --- orchestration ------------------------------------------------------


def _is_knowledge_candidate(path: Path) -> bool:
    """Excludes template/example files (e.g. profile.example.json) from ingestion."""
    return path.is_file() and ".example." not in path.name


def list_knowledge_files() -> list[str]:
    if not settings.KNOWLEDGE_DIR.exists():
        return []
    return sorted(p.name for p in settings.KNOWLEDGE_DIR.iterdir() if _is_knowledge_candidate(p))


def save_uploaded_file(filename: str, raw_bytes: bytes) -> str:
    """Validate and persist an uploaded knowledge file. Returns the saved filename."""
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.ALLOWED_KNOWLEDGE_EXTENSIONS:
        raise IngestionError(
            f"Unsupported file type '{suffix}'. Allowed: "
            f"{', '.join(sorted(settings.ALLOWED_KNOWLEDGE_EXTENSIONS))}"
        )
    if len(raw_bytes) == 0:
        raise IngestionError(f"{filename} is empty.")
    if len(raw_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise IngestionError(f"{filename} is too large.")

    if suffix == ".json":
        parse_profile_json(raw_bytes)  # validate before writing
        target = Path(settings.PROFILE_PATH)
    else:
        target = settings.KNOWLEDGE_DIR / Path(filename).name

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw_bytes)
    return target.name


def rebuild_knowledge_base() -> dict:
    """Force-reprocess every file in data/knowledge/ into the vector store,
    even ones that haven't changed. The explicit "rebuild everything" escape
    hatch (admin-triggered); sync_knowledge_base() is the cheap incremental
    path used on every app boot.

    JSON files are the structured profile (validated, left on disk as-is).
    PDF/Markdown files are extracted, normalized, chunked, and embedded.
    """
    settings.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in settings.KNOWLEDGE_DIR.iterdir() if _is_knowledge_candidate(p)]

    vectorstore = get_vectorstore()
    vectorstore.clear()

    chunks_indexed = 0
    documents_indexed = 0
    for path in sorted(files):
        suffix = path.suffix.lower()
        if suffix == ".json":
            parse_profile_json(path.read_bytes())  # surfaces validation errors
            continue
        if suffix not in {".pdf", ".md"}:
            continue

        raw = path.read_bytes()
        text = extract_text(path)
        normalized = normalize_text(text)
        chunks = chunk_text(normalized)
        if not chunks:
            logger.warning("%s produced no usable content after processing", path.name)
            continue
        chunks_indexed += vectorstore.add_documents(chunks, source=path.name, doc_hash=content_hash(raw))
        documents_indexed += 1

    return {"documents_indexed": documents_indexed, "chunks_indexed": chunks_indexed}


def sync_knowledge_base() -> dict:
    """Bring the vector store in line with data/knowledge/ on disk, without
    re-embedding anything that hasn't changed.

    A file is (re)embedded only if it's new or its content hash differs from
    what's currently indexed; vectors for files no longer on disk are purged.
    Safe (and cheap) to call on every app start.
    """
    settings.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    files = {p.name: p for p in settings.KNOWLEDGE_DIR.iterdir() if _is_knowledge_candidate(p)}
    chunkable = {name: path for name, path in files.items() if path.suffix.lower() in {".pdf", ".md"}}

    vectorstore = get_vectorstore()
    indexed = vectorstore.indexed_documents()

    for source in indexed:
        if source not in chunkable:
            vectorstore.delete_by_source(source)

    chunks_indexed = 0
    documents_indexed = 0
    documents_skipped = 0
    for name, path in sorted(chunkable.items()):
        raw = path.read_bytes()
        doc_hash = content_hash(raw)
        existing = indexed.get(name)
        if existing and existing["doc_hash"] == doc_hash:
            documents_skipped += 1
            continue

        if existing:
            vectorstore.delete_by_source(name)

        text = extract_text(path)
        normalized = normalize_text(text)
        chunks = chunk_text(normalized)
        if not chunks:
            logger.warning("%s produced no usable content after processing", path.name)
            continue
        chunks_indexed += vectorstore.add_documents(chunks, source=name, doc_hash=doc_hash)
        documents_indexed += 1

    for name, path in files.items():
        if path.suffix.lower() == ".json":
            parse_profile_json(path.read_bytes())  # surfaces validation errors

    return {
        "documents_indexed": documents_indexed,
        "documents_skipped": documents_skipped,
        "chunks_indexed": chunks_indexed,
    }
