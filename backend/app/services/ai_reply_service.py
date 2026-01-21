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
                            
                        # Generate Reply
                        reply_text = await self._generate_reply(account, msg.text, chat.id, chat.first_name, chat.username)
                        
                        if reply_text:
                            # Send reply
                            await client.send_message(chat.id, reply_text)
                            
                            # Save to DB
                            self._save_history(account.id, chat.id, chat.username, "user", msg.text)
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
            analysis = await self.llm.analyze_intent(user_msg, history_msgs)
            
            # Update Lead tags
            self._update_lead_tags(account.id, target_user_id, target_username, target_name, analysis)
            
            # Check for high value intent
            if analysis.get("is_high_value"):
                # Trigger WebSocket notification
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
                
        except Exception as e:
            logger.error(f"Intent analysis error: {e}")

        # 2. Prepare System Prompt
        system_prompt = account.persona_prompt or "You are a helpful assistant on Telegram."
        
        # 3. Call LLM for Reply
        response = await self.llm.get_response(
            prompt=user_msg,
            system_prompt=system_prompt,
            history=history_msgs
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
            # Create new lead
            lead = Lead(
                account_id=account_id,
                telegram_user_id=target_user_id,
                username=username,
                first_name=first_name,
                status="new",
                tags_json=json.dumps(tags),
                last_interaction_at=datetime.utcnow()
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
