"""
portal_captcha_templates — 客户自填 captcha 自动答题/admin DM 模板.

Phase 9 process_attempt 真 pyrogram 集成后，text_qa / admin_dm handler 需要
客户预填话术才能高效通过 captcha。Phase 10 把两列 (captcha_join_template,
captcha_intro_template) 暴露给 portal 客户表单。

Endpoints:
  GET  /portal/group-ai/captcha-templates  — 读当前两条模板
  PUT  /portal/group-ai/captcha-templates  — 更新两条模板 (None 字段不动)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.customer import Customer

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/portal/group-ai/captcha-templates",
    tags=["portal-captcha-templates"],
)

# Practical upper bounds — tight enough to fit in one Telegram message and
# discourage clients from dumping huge LLM prompts here.
MAX_JOIN_TEMPLATE_LEN = 400
MAX_INTRO_TEMPLATE_LEN = 600


class CaptchaTemplatesRead(BaseModel):
    captcha_join_template: Optional[str] = None
    captcha_intro_template: Optional[str] = None


class CaptchaTemplatesUpdate(BaseModel):
    captcha_join_template: Optional[str] = None
    captcha_intro_template: Optional[str] = None


def _validate_and_normalise(value: Optional[str], *, max_len: int,
                            field: str) -> Optional[str]:
    """Trim whitespace, treat empty string as None, enforce length cap."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > max_len:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"{field} exceeds {max_len} characters",
        )
    return stripped


@router.get("", response_model=CaptchaTemplatesRead)
async def get_captcha_templates(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> CaptchaTemplatesRead:
    row = session.get(Customer, customer.id)
    return CaptchaTemplatesRead(
        captcha_join_template=row.captcha_join_template if row else None,
        captcha_intro_template=row.captcha_intro_template if row else None,
    )


@router.put("", response_model=CaptchaTemplatesRead)
async def update_captcha_templates(
    payload: CaptchaTemplatesUpdate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> CaptchaTemplatesRead:
    """
    Partial update: only fields present (non-None) in the payload are written.
    Empty strings clear the field (set to NULL).
    """
    row = session.get(Customer, customer.id)
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="customer not found")

    updates_made = False
    if "captcha_join_template" in payload.model_fields_set:
        row.captcha_join_template = _validate_and_normalise(
            payload.captcha_join_template,
            max_len=MAX_JOIN_TEMPLATE_LEN,
            field="captcha_join_template",
        )
        updates_made = True
    if "captcha_intro_template" in payload.model_fields_set:
        row.captcha_intro_template = _validate_and_normalise(
            payload.captcha_intro_template,
            max_len=MAX_INTRO_TEMPLATE_LEN,
            field="captcha_intro_template",
        )
        updates_made = True

    if updates_made:
        session.add(row)
        session.commit()
        session.refresh(row)

    return CaptchaTemplatesRead(
        captcha_join_template=row.captcha_join_template,
        captcha_intro_template=row.captcha_intro_template,
    )
