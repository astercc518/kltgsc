import logging
from typing import List, Optional
from datetime import datetime
from sqlmodel import Session, select
from pyrogram import Client, enums
from app.models.account import Account
from app.models.chat_history import ChatHistory
from app.models.lead import Lead
from app.services.telegram_client import _create_client_and_run
from app.services.llm import LLMService
from app.services.websocket_manager import manager as ws_manager
from app.services import feature_billing as fb
from app.services.wallet_service import InsufficientBalanceError

logger = logging.getLogger(__name__)

class AIReplyService:
    def __init__(self, db_session: Session):
        self.session = db_session
        self.llm = LLMService(db_session)

    async def process_account_messages(self, account_id: int):
        """
        Check for unread messages and auto-reply using AI
        """
        account = self.session.get(Account, account_id)
        if not account or not account.auto_reply:
            return
            
        if not self.llm.is_configured():
            logger.warning("LLM not configured, skipping auto-reply")
            return

        async def op(client: Client):
            # Get dialogs with unread messages
            # Note: client.get_dialogs() is an async generator
            async for dialog in client.get_dialogs(limit=20):
                if dialog.unread_messages_count > 0:
                    chat = dialog.chat

                    # Only reply to private chats for now
                    if chat.type != enums.ChatType.PRIVATE:
                        continue

                    # Get history to find the last message
                    history = []
                    async for msg in client.get_chat_history(chat.id, limit=dialog.unread_messages_count):
                        history.append(msg)

                    # Process from oldest to newest unread
                    for msg in reversed(history):
                        if not msg.text:
                            continue

                        # Double check if it's incoming
                        if msg.outgoing:
                            continue

                        # Generate Reply（每条都生成；分支决定是发还是只存草稿）
                        reply_text = await self._generate_reply(account, msg.text, chat.id, chat.first_name, chat.username)

                        if not reply_text:
                            continue

                        # Feature billing: charge per AI generation (draft or sent).
                        # Skip if no customer context (admin pool account).
                        if account.customer_id:
                            try:
                                fb.charge(
                                    self.session,
                                    customer_id=account.customer_id,
                                    slug='auto_reply_ai',
                                    units=1,
                                    idempotency_key=f'feat:auto_reply_ai:{account.id}:{chat.id}:{msg.id}',
                                    description=f'AI 回复 acc#{account.id}',
                                )
                            except fb.FeatureNotEnabledError:
                                # Feature not opted in — generation already done,
                                # but skip the charge. Caller can still choose to send.
                                pass
                            except InsufficientBalanceError as ib_err:
                                logger.warning(
                                    f"Wallet exhausted for customer {account.customer_id}, "
                                    f"skip AI reply for lead {chat.id}: {ib_err}"
                                )
                                continue  # Don't send (would be lost work)

                        # 检查接管状态
                        lead = self.session.exec(
                            select(Lead).where(
                                Lead.account_id == account.id,
                                Lead.telegram_user_id == chat.id,
                            )
                        ).first()

                        # 总是存客户来信 history
                        self._save_history(account.id, chat.id, chat.username, "user", msg.text)

                        if lead and not lead.ai_enabled:
                            # —— 副驾驶模式：不发送，写草稿 + 推 WS ——
                            lead.ai_draft = reply_text
                            self.session.add(lead)
                            self.session.commit()
                            try:
                                await ws_manager.broadcast({
                                    "type": "ai_draft",
                                    "lead_id": lead.id,
                                    "draft": reply_text,
                                })
                            except Exception as e:
                                logger.warning(f"WS ai_draft broadcast failed: {e}")
                            # 标记已读，避免下次轮询又触发同一条
                            try:
                                await client.read_chat_history(chat.id)
                            except Exception as e:
                                logger.warning(f"read_chat_history failed: {e}")
                        else:
                            # —— 默认模式：直接发送 ——
                            await client.send_message(chat.id, reply_text)
                            self._save_history(account.id, chat.id, chat.username, "assistant", reply_text)

            return "Processed"

        try:
            await _create_client_and_run(account, op, db_session=self.session)
        except Exception as e:
            logger.error(f"Error processing messages for account {account_id}: {e}")

    async def _generate_reply(self, account: Account, user_msg: str, target_user_id: int, target_name: str, target_username: str) -> Optional[str]:
        # 1. Fetch recent history from DB
        db_history = self.session.exec(
            select(ChatHistory)
            .where(ChatHistory.account_id == account.id)
            .where(ChatHistory.target_user_id == target_user_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(10)
        ).all()
        
        # Convert to OpenAI format (reverse because we fetched desc)
        history_msgs = []
        for h in reversed(db_history):
            history_msgs.append({"role": h.role, "content": h.content})
            
        # --- Stage 9.3: Intent Recognition & Auto Tagging ---
        # Perform intent analysis on the new incoming message + history
        # We run this BEFORE generating reply, so we can potentially adjust strategy (or just notify)
        try:
            analysis = await self.llm.analyze_intent(
                user_msg, history_msgs,
                source="intent_analyze",
                account_id=account.id,
                chat_id=str(target_user_id),
            )
            
            # Update Lead tags
            self._update_lead_tags(account.id, target_user_id, target_username, target_name, analysis)
            
            # Check for high value intent
            if analysis.get("is_high_value"):
                # Trigger WebSocket notification (internal Inbox)
                await ws_manager.broadcast({
                    "type": "high_intent_alert",
                    "data": {
                        "account_id": account.id,
                        "account_phone": account.phone_number,
                        "lead_id": target_user_id,
                        "lead_name": target_name,
                        "intent": analysis.get("intent"),
                        "message": user_msg
                    }
                })

                # ── Epic 5.2: customer notification + handover timeout ──
                # Resolve the Lead row we just upserted in _update_lead_tags,
                # set takeover_deadline based on customer's configured timeout,
                # fire main_account_notifier + schedule send_handover_link task.
                try:
                    from app.models.lead import Lead as _Lead
                    from app.models.customer import Customer as _Customer
                    from datetime import datetime as _dt, timedelta as _td

                    lead_row = self.session.exec(
                        select(_Lead)
                        .where(_Lead.account_id == account.id)
                        .where(_Lead.telegram_user_id == target_user_id)
                    ).first()
                    if lead_row and account.customer_id and lead_row.takeover_deadline is None:
                        customer = self.session.get(_Customer, account.customer_id)
                        if customer:
                            timeout_min = max(1, min(30, customer.takeover_timeout_minutes or 5))
                            lead_row.takeover_deadline = _dt.utcnow() + _td(minutes=timeout_min)
                            self.session.add(lead_row)
                            self.session.commit()

                            # Best-effort: notifier + Celery timer; failures must not break reply
                            try:
                                from app.services.main_account_notifier import notify_high_intent
                                notify_high_intent.delay(lead_row.id)
                            except Exception as _e:
                                logger.warning(f"notify_high_intent enqueue failed: {_e}")
                            try:
                                from app.tasks.handover_tasks import send_handover_link_if_unclaimed
                                send_handover_link_if_unclaimed.apply_async(
                                    args=(lead_row.id,),
                                    countdown=timeout_min * 60,
                                    queue="default",
                                )
                            except Exception as _e:
                                logger.warning(f"handover task enqueue failed: {_e}")
                except Exception as e:
                    logger.warning(f"Epic 5.2 hook failed: {e}")
                
        except Exception as e:
            logger.error(f"Intent analysis error: {e}")

        # 2. Prepare System Prompt + Knowledge
        system_prompt = account.persona_prompt or "You are a helpful assistant on Telegram."
        knowledge_context = ""

        # Try to find campaign linked to this account for knowledge injection
        try:
            from app.models.campaign import Campaign
            from app.services.ai_engine import AIEngine

            campaign = None
            if account.combat_role:
                # Match account's combat_role against campaign's allowed_roles
                campaigns = self.session.exec(select(Campaign).where(Campaign.status == "active")).all()
                for c in campaigns:
                    allowed = [r.strip() for r in (c.allowed_roles or "").split(",")]
                    if account.combat_role in allowed:
                        campaign = c
                        break

            if campaign:
                # Load knowledge
                knowledge_context = AIEngine.get_campaign_knowledge(self.session, campaign.id)

                # Fallback persona from campaign if account has no persona_prompt
                if not account.persona_prompt and campaign.ai_persona_id:
                    persona_prompt = AIEngine.get_persona_prompt(self.session, campaign.ai_persona_id)
                    if persona_prompt:
                        system_prompt = persona_prompt
        except Exception as e:
            logger.error(f"Knowledge injection error: {e}")

        # Inject knowledge into system prompt if available
        if knowledge_context:
            system_prompt += f"\n\n参考知识（回答时可引用）：\n{knowledge_context}"

        # RAG：向量召回业务知识库（含手填/PDF导入/群聊抽取）
        try:
            from app.services.kb_retrieval import retrieve_relevant_kb, format_kb_for_prompt
            # Epic 5.1: tenant-scope to this account's customer (NULL = platform-wide too).
            qa_items = await retrieve_relevant_kb(
                self.session, user_msg, top_k=4,
                customer_id_filter=account.customer_id,
            )
            qa_block = format_kb_for_prompt(qa_items, max_chars=1200)
            if qa_block:
                system_prompt += f"\n\n[业务知识库召回 — 如客户提到相关内容请基于此回复]\n{qa_block}"
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")

        # 3. Call LLM for Reply
        response = await self.llm.get_response(
            prompt=user_msg,
            system_prompt=system_prompt,
            history=history_msgs,
            source="chat_reply",
            account_id=account.id,
            persona_id=account.ai_persona_id,
            chat_id=str(target_user_id),
        )

        return response

    def _update_lead_tags(self, account_id: int, target_user_id: int, username: str, first_name: str, analysis: dict):
        """
        Create or update lead record with AI analysis
        """
        import json
        
        # Find Lead
        lead = self.session.exec(
            select(Lead).where(
                Lead.account_id == account_id, 
                Lead.telegram_user_id == target_user_id
            )
        ).first()
        
        tags = analysis.get("tags", [])
        intent = analysis.get("intent")
        
        if not lead:
            # Epic D — inherit industry + customer scope from the account's
            # owning Customer so /sales/leads can filter immediately.
            from app.models.account import Account as _Acc
            from app.models.customer import Customer as _Cust
            acc_row = self.session.get(_Acc, account_id)
            cust_row = self.session.get(_Cust, acc_row.customer_id) if (acc_row and acc_row.customer_id) else None
            lead = Lead(
                account_id=account_id,
                telegram_user_id=target_user_id,
                username=username,
                first_name=first_name,
                status="new",
                tags_json=json.dumps(tags),
                last_interaction_at=datetime.utcnow(),
                customer_id=acc_row.customer_id if acc_row else None,
                industry=cust_row.industry if cust_row else None,
            )
            self.session.add(lead)
        else:
            # Update existing lead
            current_tags = json.loads(lead.tags_json) if lead.tags_json else []
            # Merge tags
            new_tags = list(set(current_tags + tags))
            # If intent is high value, maybe add intent as tag too
            if intent:
                new_tags.append(f"intent:{intent}")
                
            lead.tags_json = json.dumps(list(set(new_tags)))
            lead.last_interaction_at = datetime.utcnow()
            self.session.add(lead)
            
        self.session.commit()

    def _save_history(self, account_id: int, target_user_id: int, target_username: Optional[str], role: str, content: str):
        record = ChatHistory(
            account_id=account_id,
            target_user_id=target_user_id,
            target_username=target_username,
            role=role,
            content=content,
            created_at=datetime.utcnow()
        )
        self.session.add(record)
        self.session.commit()


# ── Phase 4a Task 2: 私聊 LLM prompt 拼群上下文 ──────────────────────────────

from app.services.group_reply_context_service import fetch_recent_group_replies_for_user  # noqa: E402


async def llm_generate(prompt: str) -> Optional[str]:
    """Thin LLM wrapper — patchable by tests, bridges to LLMService.

    实施者: 如果 ai_reply_service 内部已经有更具体的 LLM 调用入口,
    把这个 wrapper 桥接到那里。否则直接用 LLMService。
    """
    from sqlmodel import Session as _Session
    from app.core.db import engine
    return await LLMService(_Session(engine)).generate(
        prompt, source="ai_reply_with_group_ctx"
    )


def _format_group_context_block(history: list) -> str:
    if not history:
        return ""
    lines = ["你之前在群里给这位用户回复过:"]
    for i, h in enumerate(history, 1):
        lines.append(
            f"  {i}. (主题: {h.get('solution_topic', '')}) "
            f"需求点: {', '.join(h.get('extracted_needs', []))}. "
            f"回复: 「{h.get('reply_text', '')}」"
        )
    lines.append("现在他来私聊, 接住上面的话题继续聊, 不要重复自我介绍。")
    return "\n".join(lines)


async def generate_private_reply_with_context(
    *, session, customer_id: int, source_user_id: int, private_message: str,
) -> Optional[str]:
    """
    拼好群上下文 → 调 LLM 生成私聊回复。
    群 context fetch 失败 → 降级到无 context 回复, 不阻塞。
    """
    _logger = logging.getLogger(__name__)

    try:
        history = fetch_recent_group_replies_for_user(
            session=session, customer_id=customer_id,
            source_user_id=source_user_id, limit=3,
        )
    except Exception:
        _logger.exception("group context fetch failed; fallback to no-context")
        history = []

    context_block = _format_group_context_block(history)
    if context_block:
        prompt = f"{context_block}\n\n用户现在的私聊消息: 「{private_message}」\n请回复:"
    else:
        prompt = f"用户消息: 「{private_message}」\n请回复:"
    return await llm_generate(prompt)
