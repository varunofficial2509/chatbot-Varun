"""Document ingestion: extract -> normalize -> chunk -> embed -> store -> delete.

Owns everything under data/knowledge/: saving newly uploaded files and
turning PDF/Markdown files into vectors. Once a file is embedded it's
deleted from disk — the Chroma index is the durable copy, so nothing here
accumulates raw uploads over time. JSON is the one exception: it's the
structured profile, kept on disk as-is rather than chunked. Supports PDF,
Markdown, and JSON.
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


def ingest_file(path: Path) -> dict:
    """Chunk, embed, and index one PDF/Markdown file — then delete it from disk.

    The vector store is the durable copy once a document is embedded; keeping
    the raw upload around afterward would only double storage for no benefit.
    The file is removed only after a successful embed, so a failed ingest
    (bad extraction, embedding API error, ...) leaves it in place rather than
    silently losing it. Re-ingesting a name that's already indexed replaces
    its old chunks (this is how "update a document" works: upload the same
    filename again).
    """
    raw = path.read_bytes()
    doc_hash = content_hash(raw)
    text = extract_text(path)
    normalized = normalize_text(text)
    chunks = chunk_text(normalized)
    if not chunks:
        raise IngestionError(f"{path.name} produced no usable content after processing.")

    vectorstore = get_vectorstore()
    if path.name in vectorstore.indexed_documents():
        vectorstore.delete_by_source(path.name)  # replacing a prior version of this document

    chunks_indexed = vectorstore.add_documents(chunks, source=path.name, doc_hash=doc_hash)
    path.unlink()
    return {"source": path.name, "chunks_indexed": chunks_indexed}


def delete_document(source: str) -> None:
    """Remove one document's vectors from the index by its source filename."""
    get_vectorstore().delete_by_source(source)


def sync_knowledge_base() -> dict:
    """Ingest any PDF/Markdown files sitting in data/knowledge/ that haven't
    been embedded yet — e.g. dropped in directly rather than through the admin
    upload flow, which already embeds-and-deletes in one step. Each file is
    deleted from disk once indexed, so a normal run finds nothing to do here;
    the vector store itself is the source of truth, not this directory. Safe
    to call on every app start.
    """
    settings.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in settings.KNOWLEDGE_DIR.iterdir() if _is_knowledge_candidate(p)]

    chunks_indexed = 0
    documents_indexed = 0
    for path in sorted(files):
        suffix = path.suffix.lower()
        if suffix == ".json":
            parse_profile_json(path.read_bytes())  # surfaces validation errors
            continue
        if suffix not in {".pdf", ".md"}:
            continue

        result = ingest_file(path)
        chunks_indexed += result["chunks_indexed"]
        documents_indexed += 1

    return {"documents_indexed": documents_indexed, "chunks_indexed": chunks_indexed}
