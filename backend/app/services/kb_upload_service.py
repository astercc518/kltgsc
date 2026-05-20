"""
Epic 4.1 — Customer KB file upload & parsing.

Parses uploaded documents (PDF / DOCX / TXT / MD), splits into ~400-char
chunks with 60-char overlap, and inserts as customer-scoped KnowledgeBase
rows with Vertex embeddings.

Reuses chunking constants and approach from app/tasks/import_tasks.py but is
called inline (not via Celery) for immediate customer feedback. Heavy docs
(>50 pages PDF) may want a Celery-backed variant in Epic 4.2.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from sqlmodel import Session

from app.models.customer import Customer
from app.models.knowledge_base import KnowledgeBase
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# Same as import_tasks.py — keep consistent so retrieval ranks stay comparable
CHUNK_TARGET_CHARS = 400
CHUNK_OVERLAP = 60
MIN_CHUNK_CHARS = 30
MAX_CHUNKS_PER_UPLOAD = 200  # safety cap to keep one upload bounded
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown"}


@dataclass
class UploadResult:
    name: str
    total_chunks: int
    embedded_chunks: int
    skipped_short: int
    extension: str


class KBUploadError(Exception):
    """Surface to API as 400 Bad Request."""


# ── Parsers ────────────────────────────────────────────────────────────

def _parse_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise KBUploadError("pypdf not installed (server-side)") from e
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise KBUploadError("Encrypted PDFs aren't supported")
        parts: List[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception as e:  # noqa: BLE001
                logger.warning("kb_upload: PDF page extract failed: %s", e)
        return "\n\n".join(parts)
    except KBUploadError:
        raise
    except Exception as e:  # noqa: BLE001
        raise KBUploadError(f"Failed to parse PDF: {e}") from e


def _parse_docx(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError as e:
        raise KBUploadError("python-docx not installed (server-side)") from e
    try:
        doc = Document(io.BytesIO(data))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:  # noqa: BLE001
        raise KBUploadError(f"Failed to parse DOCX: {e}") from e


def _parse_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-16", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise KBUploadError("Could not decode text file with utf-8/utf-16/gbk/latin-1")


def _parse_by_extension(filename: str, data: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise KBUploadError(
            f"Unsupported file type {ext or '(no extension)'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if ext == ".pdf":
        return _parse_pdf(data)
    if ext == ".docx":
        return _parse_docx(data)
    # .txt / .md / .markdown
    return _parse_text(data)


# ── Chunking ───────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    text = text.replace("\x0c", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_into_chunks(text: str) -> List[str]:
    """Same approach as import_tasks._split_into_chunks (paragraph-aware)."""
    text = _normalize(text)
    if not text:
        return []
    chunks: List[str] = []
    paragraphs = re.split(r"\n\n+", text)
    buf = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) <= CHUNK_TARGET_CHARS:
            buf = (buf + "\n\n" + para).strip()
        else:
            if buf:
                chunks.append(buf)
            # If a single paragraph is itself larger than target, hard-split it
            while len(para) > CHUNK_TARGET_CHARS:
                chunks.append(para[:CHUNK_TARGET_CHARS])
                # Overlap to preserve sentence-spanning meaning
                para = para[CHUNK_TARGET_CHARS - CHUNK_OVERLAP:]
            buf = para
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


# ── Public API ─────────────────────────────────────────────────────────

def upload_kb_file(
    session: Session,
    customer: Customer,
    *,
    filename: str,
    data: bytes,
    category: Optional[str] = None,
    name: Optional[str] = None,
) -> UploadResult:
    """Parse → chunk → embed → insert KnowledgeBase rows scoped to customer."""
    if len(data) > MAX_FILE_BYTES:
        raise KBUploadError(
            f"File too large ({len(data)} bytes); max {MAX_FILE_BYTES} bytes"
        )

    raw_text = _parse_by_extension(filename, data)
    chunks = _split_into_chunks(raw_text)
    if not chunks:
        raise KBUploadError("Document contained no extractable text")
    chunks = chunks[:MAX_CHUNKS_PER_UPLOAD]

    es = EmbeddingService(session)
    embed_available = es.is_configured()

    base_name = name or filename
    parent_doc_id = f"upload-{customer.id}-{int(__import__('time').time())}"

    embedded = 0
    for idx, chunk in enumerate(chunks):
        emb = None
        if embed_available:
            try:
                emb = asyncio.run(
                    asyncio.wait_for(
                        es.embed(chunk, source="kb_upload"),
                        timeout=15.0,
                    )
                )
            except asyncio.TimeoutError:
                logger.warning("kb_upload: embed timed out at chunk %d", idx)
            except Exception as e:  # noqa: BLE001
                logger.warning("kb_upload: embed failed at chunk %d: %r", idx, e)

        kb = KnowledgeBase(
            name=f"{base_name} #{idx + 1}",
            description=f"Uploaded from {filename}",
            content=chunk,
            source_type="file_import",
            source_filename=filename,
            category=category or "uploaded",
            language=customer.industry or None,  # rough hint, can be re-tagged
            parent_doc_id=parent_doc_id,
            chunk_index=idx,
            customer_id=customer.id,
            embedding=emb,
        )
        session.add(kb)
        if emb is not None:
            embedded += 1

    session.commit()
    logger.info(
        "kb_upload: customer %s — %s: %d chunks, %d embedded",
        customer.id, filename, len(chunks), embedded,
    )
    return UploadResult(
        name=base_name,
        total_chunks=len(chunks),
        embedded_chunks=embedded,
        skipped_short=0,
        extension="." + filename.rsplit(".", 1)[-1].lower() if "." in filename else "",
    )
