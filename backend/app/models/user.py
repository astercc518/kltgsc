from typing import Optional
from sqlmodel import SQLModel, Field

# 角色：admin（全权）/ sales（仅 CRM + Inbox）
USER_ROLE_ADMIN = "admin"
USER_ROLE_SALES = "sales"
USER_ROLES = {USER_ROLE_ADMIN, USER_ROLE_SALES}


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    totp_secret: Optional[str] = None
    totp_enabled: bool = False
    is_active: bool = True
    is_superuser: bool = False
    role: str = Field(default=USER_ROLE_ADMIN, index=True)

    # Phase F3: industry filter for platform sales — JSON-serialized list
    # of Lead.industry values this user wants to see in /sales/inbox.
    # Empty list / NULL = no filter (see all internal-pool leads).
    industry_filter_json: str = Field(default="[]", max_length=500)
