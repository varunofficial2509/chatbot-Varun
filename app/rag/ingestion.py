"""Document ingestion: extract -> normalize -> chunk -> embed -> store.

Owns everything under data/knowledge/: saving newly uploaded files and
turning PDF/Markdown files into vectors. PDFs are deleted from disk once
embedded — the Chroma index becomes their only durable copy, so a one-off
binary upload doesn't just sit around. Markdown files are kept on disk
instead: they're meant to be hand-edited and re-synced over time (see
data/knowledge/README.md), so re-running sync on an unchanged file is a
no-op (skipped via its content hash) rather than a wasted re-embed. JSON is
the other exception: it's the structured profile, kept on disk as-is rather
than chunked. Supports PDF, Markdown, and JSON.
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
    """Chunk, embed, and index one PDF/Markdown file.

    PDFs are deleted from disk once embedded — the vector store is their
    only durable copy, and keeping the binary around afterward would only
    double storage for no benefit. Markdown files are left in place, since
    they're meant to be edited and re-synced later rather than uploaded
    once and forgotten.

    Skips re-embedding (and, for a PDF, re-deleting) a file whose content
    hash already matches what's indexed — makes it safe to call this on
    every app start without burning an embedding API call on unchanged
    Markdown files that stick around on disk. Re-ingesting a name that's
    indexed under a *different* hash replaces its old chunks (this is how
    "update a document" works: edit the file, or upload the same filename
    again, and re-sync).
    """
    raw = path.read_bytes()
    doc_hash = content_hash(raw)
    is_pdf = path.suffix.lower() == ".pdf"

    vectorstore = get_vectorstore()
    indexed = vectorstore.indexed_documents()
    current = indexed.get(path.name)
    if current and current.get("doc_hash") == doc_hash:
        if is_pdf:
            path.unlink()
        return {"source": path.name, "chunks_indexed": current["chunk_count"], "skipped": True}

    text = extract_text(path)
    normalized = normalize_text(text)
    chunks = chunk_text(normalized)
    if not chunks:
        raise IngestionError(f"{path.name} produced no usable content after processing.")

    if current:
        vectorstore.delete_by_source(path.name)  # replacing a prior version of this document

    chunks_indexed = vectorstore.add_documents(chunks, source=path.name, doc_hash=doc_hash)
    if is_pdf:
        path.unlink()
    return {"source": path.name, "chunks_indexed": chunks_indexed}


def delete_document(source: str) -> None:
    """Remove one document's vectors from the index by its source filename."""
    get_vectorstore().delete_by_source(source)


def sync_knowledge_base() -> dict:
    """(Re-)ingest the PDF/Markdown files sitting in data/knowledge/.

    PDFs disappear from disk once indexed, so a normal run only finds those
    dropped in directly rather than through the admin upload flow (which
    already embeds-and-deletes in one step). Markdown files stick around
    and get re-scanned on every call, but ingest_file skips any whose
    content hash hasn't changed since it was last indexed — so editing one
    and re-syncing (or just restarting the app) only re-embeds what
    actually changed. Safe to call on every app start.
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
        if result.get("skipped"):
            continue
        chunks_indexed += result["chunks_indexed"]
        documents_indexed += 1

    return {"documents_indexed": documents_indexed, "chunks_indexed": chunks_indexed}
