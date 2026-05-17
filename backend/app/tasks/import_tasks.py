"""
文档导入任务 — PDF → chunk → embedding → 知识库

MVP 仅支持 PDF。后续可扩展 DOCX / Markdown / URL。

Celery 任务签名：import_pdf_to_kb(file_path, category=None, source_filename=None)
"""
import asyncio
import hashlib
import logging
import os
import re
from typing import List, Optional

from celery.exceptions import SoftTimeLimitExceeded
from sqlmodel import Session as DBSession

from app.core.db import engine
from app.core.celery_app import celery_app
from app.models.knowledge_base import KnowledgeBase
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

CHUNK_TARGET_CHARS = 400  # 目标 chunk 大小（中文字符）
CHUNK_OVERLAP = 60        # chunk 间重叠，保住跨段语义
MIN_CHUNK_CHARS = 30      # 过短的 chunk 丢弃（噪声）
EMBED_BATCH_SIZE = 40


def _extract_pdf_text(file_path: str) -> List[str]:
    """
    用 pypdf 抽取 PDF 文本，返回按页的字符串列表。
    扫描件 / 加密 PDF 会得到空字符串。
    """
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("pypdf is required for PDF import") from e

    reader = PdfReader(file_path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise RuntimeError("PDF is encrypted and cannot be decrypted with empty password")

    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as e:
            logger.warning(f"PDF page extract failed: {e}")
            pages.append("")
    return pages


def _normalize(text: str) -> str:
    """合并空白、去 form feed、统一换行。"""
    text = text.replace("\x0c", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_into_chunks(text: str) -> List[str]:
    """
    切片策略：先按段落（双换行）粗切；超长段落用句号 / 换行 / 长度切；
    chunk 间重叠 CHUNK_OVERLAP 字符以保住语义。
    """
    text = _normalize(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    # 先按句号 / 换行细切，得到原子句
    atoms: List[str] = []
    for para in paragraphs:
        # 按句号 / 问号 / 感叹号 / 换行切
        sents = re.split(r"(?<=[。！？!?\.])\s+|\n+", para)
        for s in sents:
            s = s.strip()
            if not s:
                continue
            # 单句超长则硬切
            while len(s) > CHUNK_TARGET_CHARS * 2:
                atoms.append(s[:CHUNK_TARGET_CHARS])
                s = s[CHUNK_TARGET_CHARS - CHUNK_OVERLAP:]
            if s:
                atoms.append(s)

    # 聚合原子句为目标大小的 chunk
    chunks: List[str] = []
    buf = ""
    for a in atoms:
        if not buf:
            buf = a
            continue
        if len(buf) + 1 + len(a) <= CHUNK_TARGET_CHARS:
            buf = f"{buf} {a}"
        else:
            chunks.append(buf)
            # 重叠：从上一个 chunk 末尾抓 OVERLAP 字符作为新 buf 前缀
            tail = buf[-CHUNK_OVERLAP:] if CHUNK_OVERLAP and len(buf) > CHUNK_OVERLAP else ""
            buf = (tail + " " + a).strip() if tail else a

    if buf:
        chunks.append(buf)

    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


async def _embed_and_insert(
    session: DBSession,
    chunks: List[str],
    parent_doc_id: str,
    name_prefix: str,
    category: Optional[str],
    source_filename: Optional[str],
    source_url: Optional[str],
) -> int:
    """
    批量 embed + 插入。返回成功插入的 chunk 数。
    失败的 chunk（embedding 失败）仍然写入但 embedding=NULL，下次 backfill 补。
    """
    if not chunks:
        return 0

    emb_service = EmbeddingService(session)
    inserted = 0
    for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[batch_start:batch_start + EMBED_BATCH_SIZE]
        vectors: List[Optional[List[float]]]
        if emb_service.is_configured():
            vectors = await emb_service.embed_batch(batch)
        else:
            vectors = [None] * len(batch)

        for offset, (chunk_text, vec) in enumerate(zip(batch, vectors)):
            chunk_idx = batch_start + offset
            kb = KnowledgeBase(
                name=f"{name_prefix} #{chunk_idx + 1}",
                description=f"来自文档导入 · {source_filename or parent_doc_id}",
                content=chunk_text,
                source_type="file_import",
                source_filename=source_filename,
                source_url=source_url,
                parent_doc_id=parent_doc_id,
                chunk_index=chunk_idx,
                category=category,
                embedding=vec,
            )
            session.add(kb)
            inserted += 1
        session.commit()
        logger.info(f"Inserted batch {batch_start}-{batch_start + len(batch)} ({inserted} total)")
    return inserted


def _hash_file(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


@celery_app.task(bind=True, max_retries=1, soft_time_limit=1800, time_limit=2400)
def import_pdf_to_kb(
    self,
    file_path: str,
    category: Optional[str] = None,
    source_filename: Optional[str] = None,
    cleanup: bool = True,
) -> dict:
    """
    解析 PDF → chunk → embedding → 入库。
    返回 {chunks, doc_id, file}。
    """
    if not os.path.exists(file_path):
        return {"error": "file_not_found", "file": file_path}

    try:
        doc_id = _hash_file(file_path)
        display_name = source_filename or os.path.basename(file_path)
        logger.info(f"Importing PDF: {display_name} (doc_id={doc_id})")

        pages = _extract_pdf_text(file_path)
        full_text = "\n\n".join(pages)
        if not full_text.strip():
            return {
                "error": "empty_text",
                "doc_id": doc_id,
                "file": display_name,
                "hint": "PDF 没抽到任何文本，可能是扫描件 / 加密件，MVP 不支持 OCR",
            }

        chunks = _split_into_chunks(full_text)
        if not chunks:
            return {"error": "no_chunks", "doc_id": doc_id, "file": display_name}

        name_stem = os.path.splitext(display_name)[0]
        inserted = asyncio.run(
            _embed_and_insert_wrapper(
                chunks=chunks,
                parent_doc_id=doc_id,
                name_prefix=name_stem,
                category=category,
                source_filename=display_name,
                source_url=None,
            )
        )

        return {
            "ok": True,
            "doc_id": doc_id,
            "file": display_name,
            "chunks": inserted,
        }

    except SoftTimeLimitExceeded:
        logger.error(f"Import timeout: {file_path}")
        raise
    except Exception as e:
        logger.exception(f"PDF import failed: {e}")
        return {"error": "exception", "detail": str(e), "file": file_path}
    finally:
        if cleanup:
            try:
                os.remove(file_path)
            except OSError:
                pass


async def _embed_and_insert_wrapper(
    chunks: List[str],
    parent_doc_id: str,
    name_prefix: str,
    category: Optional[str],
    source_filename: Optional[str],
    source_url: Optional[str],
) -> int:
    """async 包裹层：开 session 跑 _embed_and_insert。"""
    with DBSession(engine) as session:
        return await _embed_and_insert(
            session=session,
            chunks=chunks,
            parent_doc_id=parent_doc_id,
            name_prefix=name_prefix,
            category=category,
            source_filename=source_filename,
            source_url=source_url,
        )
