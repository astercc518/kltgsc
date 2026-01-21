import json
import logging
from typing import List, Dict, Optional
from sqlmodel import Session
from app.services.llm import LLMService
from app.models.script import Script

logger = logging.getLogger(__name__)

class ScriptService:
    def __init__(self, db_session: Session):
        self.session = db_session
        self.llm = LLMService(db_session)

    async def generate_script_lines(self, script_id: int) -> Optional[List[Dict[str, str]]]:
        """
        Generate dialogue lines for a script using LLM
        """
        script = self.session.get(Script, script_id)
        if not script:
            raise ValueError("Script not found")
            
        if not self.llm.is_configured():
            raise ValueError("LLM not configured")

        roles = json.loads(script.roles_json) # [{"name": "UserA", "prompt": "..."}]
        
        # Construct prompt
        system_prompt = "You are a creative scriptwriter for Telegram group conversations."
        
        user_prompt = f"""
        Generate a natural conversation between {len(roles)} people about the topic: "{script.topic}".
        
        Roles:
        """
        for r in roles:
            user_prompt += f"- {r['name']}: {r.get('prompt', 'Participant')}\n"
            
        user_prompt += """
        Format the output as a JSON array of objects, where each object has "role", "content", and optionally "reply_to_line_index" (integer index of the line to reply to, or null).
        Example:
        [
            {"role": "UserA", "content": "Hello everyone!", "reply_to_line_index": null},
            {"role": "UserB", "content": "Hi! How are you?", "reply_to_line_index": 0}
        ]
        The conversation should have about 10-15 turns. Keep it casual and realistic. Use "reply_to_line_index" when a user is directly replying to a previous specific message to create threads.
        Only output the JSON array, nothing else.
        """
        
        try:
            response = await self.llm.get_response(user_prompt, system_prompt)
            if not response:
                raise ValueError("Empty response from LLM")
                
            # Clean up response (sometimes LLM wraps code in markdown blocks)
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            
            lines = json.loads(cleaned_response)
            
            # Validate structure
            if not isinstance(lines, list):
                raise ValueError("LLM output is not a list")
                
            script.lines_json = json.dumps(lines)
            self.session.add(script)
            self.session.commit()
            
            return lines
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response: {response}")
            raise ValueError("Failed to parse LLM response as JSON")
        except Exception as e:
            logger.error(f"Script generation error: {e}")
            raise e
