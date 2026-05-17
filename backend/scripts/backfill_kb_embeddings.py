"""
为已存在但 embedding IS NULL 的 ai_knowledge_base 行回填向量。

幂等：可重复跑，每次只处理 embedding 为 NULL 的行。
失败的行保持 NULL，下次再补。

使用：
    docker compose exec backend python scripts/backfill_kb_embeddings.py
    # 指定批次大小：
    docker compose exec backend python scripts/backfill_kb_embeddings.py --batch-size 50
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 让脚本能从任意目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.models.knowledge_base import KnowledgeBase  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")


def build_text_for_embedding(kb: KnowledgeBase) -> str:
    """优先用 qa_question + qa_answer；否则用 content；都没有就用 name + description。"""
    parts = []
    if kb.qa_question:
        parts.append(kb.qa_question.strip())
    if kb.qa_answer:
        parts.append(kb.qa_answer.strip())
    if not parts:
        if kb.content:
            parts.append(kb.content.strip())
        else:
            if kb.name:
                parts.append(kb.name.strip())
            if kb.description:
                parts.append(kb.description.strip())
    return "\n".join(parts).strip()


async def backfill(batch_size: int = 50, max_rows: int = 0, rpm: int = 0) -> None:
    """
    rpm=0 表示不限速；否则在每个 batch 后 sleep 以保证 ≤ rpm 请求/分钟。
    Gemini 免费档 embed_content = 100 RPM，建议 --rpm 90 留余量。
    """
    sleep_between = (60.0 / rpm) if rpm > 0 else 0.0
    with Session(engine) as session:
        emb = EmbeddingService(session)
        if not emb.is_configured():
            logger.error("Embedding service not configured; aborting")
            return

        # 限速时强制串行（不能 5 并发否则瞬时突发 5 个 = 仍然 429）
        if rpm > 0:
            import app.services.embedding_service as es
            es.MAX_CONCURRENCY = 1
            emb._sem = asyncio.Semaphore(1)
            logger.info(f"Rate-limited mode: {rpm} RPM, ~{sleep_between:.2f}s between batches")

        total_done = 0
        while True:
            rows = session.exec(
                select(KnowledgeBase)
                .where(KnowledgeBase.embedding.is_(None))
                .limit(batch_size)
            ).all()

            if not rows:
                logger.info("All KB rows have embeddings. Done.")
                break

            texts = [build_text_for_embedding(kb) for kb in rows]
            non_empty = [(i, t) for i, t in enumerate(texts) if t]
            if not non_empty:
                # 全是空文本，标记为 skipped 避免死循环
                logger.warning(
                    f"Batch of {len(rows)} rows has no usable text; "
                    f"setting placeholders to skip"
                )
                for kb in rows:
                    # 写一个无意义的全零向量占位，下次不再选中
                    kb.embedding = [0.0] * 768
                    session.add(kb)
                session.commit()
                continue

            vectors = await emb.embed_batch([t for _, t in non_empty])

            ok = 0
            for (orig_idx, _), vec in zip(non_empty, vectors):
                if vec:
                    rows[orig_idx].embedding = vec
                    session.add(rows[orig_idx])
                    ok += 1

            session.commit()
            total_done += ok
            logger.info(f"Embedded {ok}/{len(rows)} in batch; total done: {total_done}")

            if max_rows and total_done >= max_rows:
                logger.info(f"Hit max_rows={max_rows}, stopping")
                break

            if sleep_between > 0:
                await asyncio.sleep(sleep_between)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-rows", type=int, default=0, help="0 = no limit")
    parser.add_argument("--rpm", type=int, default=0,
                        help="Throttle to ≤ this many requests/minute. "
                             "Gemini 免费档限 100 RPM；建议 90。"
                             "0 = no limit（适合付费档）。")
    args = parser.parse_args()
    asyncio.run(backfill(args.batch_size, args.max_rows, args.rpm))


if __name__ == "__main__":
    main()
