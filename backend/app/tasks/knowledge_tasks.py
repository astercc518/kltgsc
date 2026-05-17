"""
知识库采集任务
- scrape_account_groups: 用指定账号拉取所有群+私聊消息历史，落库到 GroupMessage
"""
import asyncio
import json
import logging
import time
from typing import Optional
from datetime import datetime

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import func
from sqlmodel import Session as DBSession, select

from app.core.db import engine
from app.core.celery_app import celery_app
from app.models.account import Account
from app.models.group_message import GroupMessage
from app.models.knowledge_base import KnowledgeBase
from app.models.scraping_task import ScrapingTask
from app.services.telegram_client import _create_client_and_run

logger = logging.getLogger(__name__)


def _classify_chat(chat) -> Optional[str]:
    """返回我们关心的 chat_type，否则返回 None 表示跳过"""
    t = str(chat.type).lower()  # ChatType.SUPERGROUP -> 'chattype.supergroup'
    if "supergroup" in t:
        return "supergroup"
    if "group" in t and "super" not in t:
        return "group"
    if t.endswith("private"):
        return "private"
    # channel / bot 跳过
    return None


def _extract_text(msg) -> str:
    """优先 text，然后 caption；都无返回空字符串"""
    if getattr(msg, "text", None):
        return str(msg.text)
    if getattr(msg, "caption", None):
        return str(msg.caption)
    return ""


def _media_type(msg) -> Optional[str]:
    for attr in ("photo", "video", "document", "voice", "audio", "sticker", "animation"):
        if getattr(msg, attr, None):
            return attr
    return None


@celery_app.task(bind=True, max_retries=1, soft_time_limit=21600, time_limit=28800)
def scrape_account_groups(
    self,
    account_id: int,
    scraping_task_id: Optional[int] = None,
    include_private: bool = True,
    limit_per_chat: Optional[int] = None,
    chat_sleep_sec: float = 2.0,
    msg_batch_size: int = 200,
):
    """
    用指定账号采集其参与的所有群组/私聊消息历史，落库 GroupMessage。
    增量逻辑：每个 chat 查询当前 DB 最大 message_id，超过部分才入库。

    参数:
      account_id: 用哪个账号采（一般是主业务号 81）
      scraping_task_id: 进度跟踪记录
      include_private: 是否包含私聊
      limit_per_chat: 每个 chat 最多采多少条（None=全量）
      chat_sleep_sec: chat 之间停顿秒数（防 FloodWait）
      msg_batch_size: 每多少条落一次盘
    """
    logger.info(f"scrape_account_groups start: account={account_id}, include_private={include_private}, limit_per_chat={limit_per_chat}")

    db = DBSession(engine)
    progress = {
        "total_chats": 0,
        "processed_chats": 0,
        "total_messages": 0,
        "current_chat": None,
        "errors": [],
    }

    def _save_progress():
        if not scraping_task_id:
            return
        st = db.get(ScrapingTask, scraping_task_id)
        if st:
            st.result_json = json.dumps(progress, ensure_ascii=False)
            st.status = "running"
            db.add(st)
            db.commit()

    try:
        account = db.get(Account, account_id)
        if not account:
            return {"success": False, "error": f"Account {account_id} not found"}

        async def op(client):
            from pyrogram.errors import FloodWait

            # 1. 拉所有 dialog
            dialogs = []
            async for dialog in client.get_dialogs():
                ct = _classify_chat(dialog.chat)
                if not ct:
                    continue
                if ct == "private" and not include_private:
                    continue
                dialogs.append((dialog.chat, ct))

            progress["total_chats"] = len(dialogs)
            _save_progress()
            logger.info(f"Found {len(dialogs)} chats to scrape (account {account_id})")

            # 2. 逐个 chat 抓历史
            for chat, chat_type in dialogs:
                chat_title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(chat.id)
                progress["current_chat"] = f"{chat_title} ({chat.id})"
                logger.info(f"Scraping {chat_title} ({chat.id}, {chat_type})")

                # 增量：查当前最大 message_id
                max_existing = db.exec(
                    select(func.max(GroupMessage.message_id)).where(
                        GroupMessage.account_id == account_id,
                        GroupMessage.chat_id == chat.id,
                    )
                ).first() or 0

                buffer = []
                count = 0
                stopped = False
                try:
                    async for msg in client.get_chat_history(chat.id):
                        if msg.empty or msg.service:
                            continue
                        if max_existing and msg.id <= max_existing:
                            stopped = True
                            break
                        if limit_per_chat and count >= limit_per_chat:
                            stopped = True
                            break

                        text = _extract_text(msg)
                        if not text.strip():
                            continue

                        sender = getattr(msg, "from_user", None)
                        sender_id = sender.id if sender else None
                        sender_username = sender.username if sender else None
                        sender_name = None
                        if sender:
                            parts = [sender.first_name or "", sender.last_name or ""]
                            sender_name = " ".join(p for p in parts if p) or None

                        gm = GroupMessage(
                            account_id=account_id,
                            chat_id=chat.id,
                            chat_title=chat_title,
                            chat_type=chat_type,
                            chat_username=getattr(chat, "username", None),
                            message_id=msg.id,
                            sender_id=sender_id,
                            sender_username=sender_username,
                            sender_name=sender_name,
                            content=text,
                            reply_to_msg_id=getattr(msg, "reply_to_message_id", None),
                            has_media=bool(_media_type(msg)),
                            media_type=_media_type(msg),
                            message_date=msg.date if hasattr(msg, "date") and msg.date else datetime.utcnow(),
                        )
                        buffer.append(gm)
                        count += 1

                        if len(buffer) >= msg_batch_size:
                            db.add_all(buffer)
                            try:
                                db.commit()
                            except Exception as e:
                                db.rollback()
                                logger.warning(f"batch insert conflict (likely duplicates), falling back to per-row: {e}")
                                for g in buffer:
                                    db.add(g)
                                    try:
                                        db.commit()
                                    except Exception:
                                        db.rollback()
                            buffer = []
                            await asyncio.sleep(0.5)

                except FloodWait as fw:
                    logger.warning(f"FloodWait {fw.value}s on chat {chat.id}, sleeping then continuing")
                    await asyncio.sleep(min(fw.value, 60))
                    progress["errors"].append({"chat": chat_title, "error": f"FloodWait {fw.value}s"})

                # flush 余下
                if buffer:
                    db.add_all(buffer)
                    try:
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        for g in buffer:
                            db.add(g)
                            try:
                                db.commit()
                            except Exception:
                                db.rollback()

                progress["processed_chats"] += 1
                progress["total_messages"] += count
                _save_progress()
                logger.info(f"Done {chat_title}: +{count} new messages (stopped early: {stopped})")

                await asyncio.sleep(chat_sleep_sec)

            return {"chats": progress["total_chats"], "messages": progress["total_messages"]}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success, result = loop.run_until_complete(
                _create_client_and_run(account, op, db_session=db)
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if scraping_task_id:
            st = db.get(ScrapingTask, scraping_task_id)
            if st:
                st.status = "completed" if success else "failed"
                st.result_json = json.dumps(progress, ensure_ascii=False)
                st.completed_at = datetime.utcnow()
                if not success:
                    st.error_message = str(result)[:500]
                db.add(st)
                db.commit()

        return {"success": success, "result": result, "progress": progress}

    except SoftTimeLimitExceeded:
        logger.error(f"scrape_account_groups timed out on account {account_id}")
        if scraping_task_id:
            st = db.get(ScrapingTask, scraping_task_id)
            if st:
                st.status = "failed"
                st.error_message = "Soft time limit exceeded"
                st.result_json = json.dumps(progress, ensure_ascii=False)
                db.add(st)
                db.commit()
        return {"success": False, "error": "timeout", "progress": progress}

    except Exception as e:
        logger.exception(f"scrape_account_groups failed: {e}")
        if scraping_task_id:
            st = db.get(ScrapingTask, scraping_task_id)
            if st:
                st.status = "failed"
                st.error_message = str(e)[:500]
                st.result_json = json.dumps(progress, ensure_ascii=False)
                db.add(st)
                db.commit()
        return {"success": False, "error": str(e), "progress": progress}
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────────
# Phase 2: Q&A 抽取任务
# ────────────────────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=1, soft_time_limit=14400, time_limit=18000)
def extract_qa_from_messages(
    self,
    chat_ids: Optional[list] = None,
    window_size: int = 50,
    concurrency: int = 3,
    scraping_task_id: Optional[int] = None,
    max_windows: Optional[int] = None,
):
    """
    扫描 group_message 表里 qa_extracted=false 的消息，按 chat 分组、按时间窗口切片，
    调 Gemini 抽取 Q&A 对，写入 KnowledgeBase（source_type='qa_extracted'）。

    参数:
      chat_ids: 限定只处理这些 chat（None=全部）
      window_size: 每个窗口包含多少条消息送给 LLM
      concurrency: LLM 并发数（防超 RPM）
      max_windows: 最多处理多少个窗口（None=全部）
    """
    import asyncio
    from app.services.llm import LLMService
    from app.services.qa_extractor import extract_qa_from_window

    logger.info(f"extract_qa_from_messages start: chat_ids={chat_ids}, window={window_size}, concurrency={concurrency}")

    db = DBSession(engine)
    stats = {
        "windows_processed": 0,
        "qa_extracted": 0,
        "chats_touched": 0,
        "errors": 0,
    }

    def _save_progress():
        if not scraping_task_id:
            return
        st = db.get(ScrapingTask, scraping_task_id)
        if st:
            st.result_json = json.dumps(stats, ensure_ascii=False)
            st.status = "running"
            db.add(st)
            db.commit()

    try:
        llm = LLMService(db_session=db)
        if not llm.is_configured():
            return {"success": False, "error": "LLM service not configured"}

        # 1. 取出所有有未抽 QA 消息的 chat
        chat_q = select(GroupMessage.chat_id, GroupMessage.chat_title, GroupMessage.chat_type).where(
            GroupMessage.qa_extracted == False
        )
        if chat_ids:
            chat_q = chat_q.where(GroupMessage.chat_id.in_(chat_ids))
        chat_q = chat_q.distinct()
        chat_rows = db.exec(chat_q).all()
        logger.info(f"Found {len(chat_rows)} chats with pending messages")

        async def _process_window(chat_id, chat_title, chat_type, window_msgs):
            try:
                payload = [
                    {
                        "date": m.message_date,
                        "sender_name": m.sender_name,
                        "sender_username": m.sender_username,
                        "sender_id": m.sender_id,
                        "content": m.content,
                        "reply_to": m.reply_to_msg_id,
                    }
                    for m in window_msgs
                ]
                qa_list = await extract_qa_from_window(llm, chat_title, chat_type, payload)
                return chat_id, chat_title, window_msgs, qa_list
            except Exception as e:
                logger.warning(f"window extraction failed (chat {chat_id}): {e}")
                stats["errors"] += 1
                return chat_id, chat_title, window_msgs, []

        async def _run():
            sem = asyncio.Semaphore(concurrency)

            async def _bounded(coro):
                async with sem:
                    return await coro

            window_count = 0
            for chat_id, chat_title, chat_type in chat_rows:
                if max_windows and window_count >= max_windows:
                    break
                # 拿该 chat 所有未抽消息（按时间升序）
                msgs = db.exec(
                    select(GroupMessage)
                    .where(GroupMessage.chat_id == chat_id, GroupMessage.qa_extracted == False)
                    .order_by(GroupMessage.message_date.asc())
                ).all()
                if not msgs:
                    continue
                stats["chats_touched"] += 1

                # 切窗
                windows = [msgs[i:i + window_size] for i in range(0, len(msgs), window_size)]
                if max_windows:
                    windows = windows[: max_windows - window_count]

                tasks_ = [
                    _bounded(_process_window(chat_id, chat_title, chat_type, w))
                    for w in windows
                ]
                results = await asyncio.gather(*tasks_, return_exceptions=False)

                # 落 KB + 标记消息
                for cid, ctitle, win_msgs, qa_list in results:
                    for qa in qa_list:
                        tags_str = json.dumps(qa.get("tags", []), ensure_ascii=False)
                        content_md = f"**Q:** {qa['question']}\n\n**A:** {qa['answer']}"
                        kb = KnowledgeBase(
                            name=qa["question"][:100],
                            description=f"来自群「{ctitle}」· 主题：{qa['topic']}",
                            content=content_md,
                            source_type="qa_extracted",
                            source_chat_id=cid,
                            source_chat_title=ctitle,
                            qa_question=qa["question"],
                            qa_answer=qa["answer"],
                            qa_topic=qa["topic"],
                            qa_tags=tags_str,
                        )
                        db.add(kb)
                        stats["qa_extracted"] += 1
                    # 标记
                    for m in win_msgs:
                        m.qa_extracted = True
                        db.add(m)
                    try:
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        logger.error(f"KB insert failed for chat {cid}: {e}")
                        stats["errors"] += 1

                    stats["windows_processed"] += 1
                    window_count += 1
                    _save_progress()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if scraping_task_id:
            st = db.get(ScrapingTask, scraping_task_id)
            if st:
                st.status = "completed"
                st.completed_at = datetime.utcnow()
                st.result_json = json.dumps(stats, ensure_ascii=False)
                db.add(st)
                db.commit()

        logger.info(f"extract_qa_from_messages done: {stats}")
        return {"success": True, "stats": stats}

    except SoftTimeLimitExceeded:
        logger.error("extract_qa_from_messages timed out")
        if scraping_task_id:
            st = db.get(ScrapingTask, scraping_task_id)
            if st:
                st.status = "failed"
                st.error_message = "Soft time limit exceeded"
                st.result_json = json.dumps(stats, ensure_ascii=False)
                db.add(st)
                db.commit()
        return {"success": False, "error": "timeout", "stats": stats}

    except Exception as e:
        logger.exception(f"extract_qa_from_messages failed: {e}")
        if scraping_task_id:
            st = db.get(ScrapingTask, scraping_task_id)
            if st:
                st.status = "failed"
                st.error_message = str(e)[:500]
                db.add(st)
                db.commit()
        return {"success": False, "error": str(e), "stats": stats}
    finally:
        db.close()
