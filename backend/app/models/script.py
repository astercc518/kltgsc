from typing import Optional, List, Dict
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
import json

class ScriptBase(SQLModel):
    name: str
    description: Optional[str] = None
    topic: str # The topic for LLM to generate dialogue
    roles_json: str = "[]" # List of dicts: [{"name": "A", "prompt": "..."}]
    lines_json: Optional[str] = None # Generated lines: [{"role": "A", "content": "...", "reply_to_role": "B"}]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Script(ScriptBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tasks: List["ScriptTask"] = Relationship(back_populates="script")

class ScriptCreate(ScriptBase):
    pass

class ScriptRead(ScriptBase):
    id: int

class ScriptTaskBase(SQLModel):
    script_id: int = Field(foreign_key="script.id")
    target_group: str
    account_mapping_json: str = "{}" # Map role_name -> account_id
    status: str = Field(default="pending") # pending, running, completed, failed
    current_step: int = Field(default=0)
    min_delay: int = 5
    max_delay: int = 15
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ScriptTask(ScriptTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    script: Optional[Script] = Relationship(back_populates="tasks")

class ScriptTaskCreate(ScriptTaskBase):
    pass

class ScriptTaskRead(ScriptTaskBase):
    id: int
