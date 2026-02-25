from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    totp_secret: Optional[str] = None
    totp_enabled: bool = False
    is_active: bool = True
    is_superuser: bool = False
