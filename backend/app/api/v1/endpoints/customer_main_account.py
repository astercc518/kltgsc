"""
Epic 5.0 — Customer main-account QR login endpoints.

Auth: get_active_customer (must have paid subscription before binding main account).

Flow from frontend MainAccount.tsx:
    1. POST /customer/main-account/qr/start  → token + qr_url + qr_png_b64
    2. (display QR; user scans on phone)
    3. GET  /customer/main-account/qr/status?token=  every 2s
       state transitions: pending → password_required? → success / expired / error
    4. if password_required: POST /customer/main-account/qr/password
    5. on success: GET /customer/main-account shows the bound account info

The api_id/api_hash come from settings (already used elsewhere for registration);
each customer borrows the platform pair (same model as auto_register).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.api.deps_customer import get_active_customer
from app.core.db import get_session
from app.models.account import Account
from app.models.customer import Customer
from app.services import qr_login_service

logger = logging.getLogger(__name__)
router = APIRouter()


class QRStartResponse(BaseModel):
    token: str
    qr_url: str
    qr_png_b64: str
    expires_at: float
    state: str
    mock: bool = False


class QRStatusResponse(BaseModel):
    token: str
    state: str
    error: Optional[str] = None
    expires_at: Optional[float] = None
    username: Optional[str] = None
    phone_last4: Optional[str] = None


class QRPasswordRequest(BaseModel):
    token: str
    password: str


class MainAccountStatus(BaseModel):
    connected: bool
    account_id: Optional[int] = None
    phone_last4: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    connected_at: Optional[datetime] = None
    status: Optional[str] = None  # active / disconnected


# ── api_id / api_hash sourcing ──────────────────────────────────────────

def _get_api_credentials(session: Session) -> tuple[int, str]:
    """Pull api_id/api_hash from system_config (same pattern as auto_register)."""
    from app.models.system_config import SystemConfig
    from sqlmodel import select

    api_id_row = session.exec(
        select(SystemConfig).where(SystemConfig.key == "api_id")
    ).first()
    api_hash_row = session.exec(
        select(SystemConfig).where(SystemConfig.key == "api_hash")
    ).first()
    api_id = int(api_id_row.value) if api_id_row and api_id_row.value else 0
    api_hash = api_hash_row.value if api_hash_row else ""
    return api_id, api_hash


# ── Endpoints ───────────────────────────────────────────────────────────

@router.post("/qr/start", response_model=QRStartResponse, status_code=201)
async def start_qr(
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    api_id, api_hash = _get_api_credentials(session)
    if not qr_login_service.MOCK_MODE and (not api_id or not api_hash):
        raise HTTPException(
            status_code=503,
            detail="Telegram API credentials (api_id/api_hash) not configured. "
                   "Set them via /api/v1/system/config or run with MOCK_QR_AUTOACCEPT=1.",
        )
    result = await qr_login_service.start_qr(customer.id, api_id, api_hash)
    return result


@router.get("/qr/status", response_model=QRStatusResponse)
def qr_status(
    token: str,
    _customer: Customer = Depends(get_active_customer),
) -> Any:
    state = qr_login_service.get_state(token)
    return state


@router.post("/qr/password")
def qr_password(
    payload: QRPasswordRequest,
    _customer: Customer = Depends(get_active_customer),
) -> Any:
    result = qr_login_service.submit_password(payload.token, payload.password)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason"))
    return result


@router.get("", response_model=MainAccountStatus)
def get_main_account(
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    if not customer.main_account_id:
        return MainAccountStatus(connected=False)
    acc = session.get(Account, customer.main_account_id)
    if not acc:
        return MainAccountStatus(connected=False)
    return MainAccountStatus(
        connected=True,
        account_id=acc.id,
        phone_last4=(acc.phone_number or "")[-4:],
        username=None,  # we don't currently store TG username on Account; could
        first_name=None,
        connected_at=acc.created_at,
        status=acc.status,
    )


@router.delete("")
def disconnect_main_account(
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    if not customer.main_account_id:
        return {"disconnected": False, "reason": "no main account bound"}
    acc = session.get(Account, customer.main_account_id)
    if acc:
        acc.is_customer_main = False
        acc.status = "disconnected"
        # Wipe the session string for safety (customer can rescan to rebind)
        acc.session_string = None
        acc.session_string_encrypted = False
        session.add(acc)
    customer.main_account_id = None
    customer.updated_at = datetime.utcnow()
    session.add(customer)
    session.commit()
    logger.info("Main account disconnected for customer %s", customer.id)
    return {"disconnected": True}
