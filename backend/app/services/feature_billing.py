"""
Feature Billing — 统一的 feature 权限 + 按用量扣费 service。

所有业务模块（marketing / scraping / invite / kb / ai_reply 等）通过这个
service 完成两件事：
1. **权限**：客户是否开通了某个功能（feature_slug）
2. **扣费**：按 units 数量调用 wallet_service.charge_wallet() 扣余额

规则：
- 全局默认价定义在 feature_registry.default_price_cents
- 客户单价覆盖在 customer_feature.custom_price_cents（NULL = 用默认）
- 客户启用/禁用在 customer_feature.enabled；没记录则回退到 feature_registry.enabled_by_default
- 余额不足拒绝调用（抛 InsufficientBalanceError）
- 幂等通过 wallet_transaction.idempotency_key UNIQUE 约束

参考 /root/.claude/plans/groovy-strolling-canyon.md
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app.models.feature import (
    FeatureRegistry,
    CustomerFeature,
)
from app.models.wallet import WalletTransaction
from app.services.wallet_service import (
    InsufficientBalanceError,
    WalletError,
    charge_wallet,
    get_balance_cents,
)


class FeatureBillingError(Exception):
    """Base class for feature-billing related errors (mapped to 400 by default)."""


class FeatureNotEnabledError(FeatureBillingError):
    """客户未开通该 feature（mapped to 403 by API layer）."""


class UnknownFeatureError(FeatureBillingError):
    """feature_slug 不在 registry 里或被软下架（400）."""


# ── Resolution helpers ─────────────────────────────────────────────────


def _get_registry(session: Session, slug: str) -> FeatureRegistry:
    """获取 registry 行；不存在或软下架抛错。"""
    reg = session.get(FeatureRegistry, slug)
    if reg is None:
        raise UnknownFeatureError(f"Feature '{slug}' not registered")
    if not reg.is_active:
        raise UnknownFeatureError(f"Feature '{slug}' is currently inactive")
    return reg


def _get_customer_override(
    session: Session, customer_id: int, slug: str,
) -> Optional[CustomerFeature]:
    """获取该客户对该 feature 的 override 行，没有则 None。"""
    return session.exec(
        select(CustomerFeature).where(
            CustomerFeature.customer_id == customer_id,
            CustomerFeature.feature_slug == slug,
        )
    ).first()


# ── Public API ─────────────────────────────────────────────────────────


def is_enabled(session: Session, customer_id: int, slug: str) -> bool:
    """该客户是否开通了 feature。

    规则:
    - customer_feature 行 + enabled=true → True
    - customer_feature 行 + enabled=false → False（被显式禁用）
    - 无 customer_feature 行 → 用 registry.enabled_by_default
    - registry 不存在或软下架 → False（不抛错，让 caller 用 require_enabled 显式 enforce）
    """
    try:
        reg = _get_registry(session, slug)
    except UnknownFeatureError:
        return False

    override = _get_customer_override(session, customer_id, slug)
    if override is not None:
        return override.enabled

    return reg.enabled_by_default


def get_unit_price_cents(session: Session, customer_id: int, slug: str) -> int:
    """该客户该 feature 的实际单价：override > default。"""
    reg = _get_registry(session, slug)
    override = _get_customer_override(session, customer_id, slug)
    if override is not None and override.custom_price_cents is not None:
        return override.custom_price_cents
    return reg.default_price_cents


def estimate_cost_cents(
    session: Session, customer_id: int, slug: str, units: int,
) -> int:
    """成本预估 = 单价 × units。不做余额/启用检查。"""
    if units < 0:
        raise ValueError("units must be non-negative")
    unit = get_unit_price_cents(session, customer_id, slug)
    return unit * units


def check_can_afford(
    session: Session, customer_id: int, slug: str, units: int,
) -> None:
    """启动批量任务前的 pre-flight check。

    抛出:
      - UnknownFeatureError（400）
      - FeatureNotEnabledError（403）— 客户没开通
      - InsufficientBalanceError（402）— 余额不够
    """
    if not is_enabled(session, customer_id, slug):
        raise FeatureNotEnabledError(
            f"Feature '{slug}' is not enabled for customer {customer_id}"
        )
    total_cents = estimate_cost_cents(session, customer_id, slug, units)
    balance = get_balance_cents(session, customer_id)
    if balance < total_cents:
        raise InsufficientBalanceError(
            f"Need {total_cents}c for {units} units of '{slug}', balance is {balance}c"
        )


def require_enabled(session: Session, customer_id: int, slug: str) -> None:
    """便捷断言：仅检查 enabled，不检查余额。

    用于读类 API（如 GET /customer/usage 按 feature 过滤时）。
    """
    if not is_enabled(session, customer_id, slug):
        raise FeatureNotEnabledError(
            f"Feature '{slug}' is not enabled for customer {customer_id}"
        )


def charge(
    session: Session,
    customer_id: int,
    slug: str,
    units: int,
    idempotency_key: str,
    description: str = "",
    bulk_batch_id: Optional[int] = None,
) -> WalletTransaction:
    """实际扣费。返回 WalletTransaction。

    扣费前会:
      1. 校验 feature 已开通（FeatureNotEnabledError）
      2. 计算 unit_price × units → total_cents
      3. 走 wallet_service.charge_wallet() （行锁 + idempotency）

    如果 idempotency_key 已存在 → 返回已有 transaction 不二次扣费。
    余额不足 → InsufficientBalanceError 由 wallet_service 抛出。
    """
    if units <= 0:
        raise ValueError("units must be positive")

    if not is_enabled(session, customer_id, slug):
        raise FeatureNotEnabledError(
            f"Feature '{slug}' is not enabled for customer {customer_id}"
        )

    reg = _get_registry(session, slug)
    unit_price = get_unit_price_cents(session, customer_id, slug)
    total_cents = unit_price * units

    if not description:
        description = (
            f"{reg.name_zh} × {units} {reg.billing_unit} "
            f"@ {unit_price}¢"
        )

    return charge_wallet(
        session,
        customer_id=customer_id,
        amount_cents=total_cents,
        idempotency_key=idempotency_key,
        description=description[:200],
        bulk_batch_id=bulk_batch_id,
    )


# ── Read helpers (for API layer) ───────────────────────────────────────


def list_registry_active(session: Session) -> list[FeatureRegistry]:
    """列出全部 active feature（admin 全局定价用）。"""
    return list(session.exec(
        select(FeatureRegistry)
        .where(FeatureRegistry.is_active == True)  # noqa: E712
        .order_by(FeatureRegistry.category, FeatureRegistry.slug)
    ).all())


def list_customer_features(session: Session, customer_id: int) -> list[dict]:
    """返回客户视角的 feature 列表（含解析后的单价 + enabled 状态）。

    格式参考 CustomerFeatureRead schema。
    """
    registry = list_registry_active(session)
    overrides = {
        cf.feature_slug: cf
        for cf in session.exec(
            select(CustomerFeature).where(CustomerFeature.customer_id == customer_id)
        ).all()
    }

    result = []
    for reg in registry:
        override = overrides.get(reg.slug)
        if override is not None:
            enabled = override.enabled
            price = (
                override.custom_price_cents
                if override.custom_price_cents is not None
                else reg.default_price_cents
            )
            is_custom = override.custom_price_cents is not None
            notes = override.notes
        else:
            enabled = reg.enabled_by_default
            price = reg.default_price_cents
            is_custom = False
            notes = ""

        result.append({
            "feature_slug": reg.slug,
            "name_zh": reg.name_zh,
            "name_en": reg.name_en,
            "category": reg.category,
            "billing_unit": reg.billing_unit,
            "enabled": enabled,
            "unit_price_cents": price,
            "is_custom_price": is_custom,
            "notes": notes,
        })
    return result


def upsert_customer_feature(
    session: Session,
    customer_id: int,
    slug: str,
    enabled: bool,
    custom_price_cents: Optional[int] = None,
    notes: str = "",
    granted_by_user_id: Optional[int] = None,
) -> CustomerFeature:
    """admin 设置某客户某 feature。已有行 → update，无行 → insert。"""
    # 校验 feature 存在
    _get_registry(session, slug)

    existing = _get_customer_override(session, customer_id, slug)
    if existing:
        existing.enabled = enabled
        existing.custom_price_cents = custom_price_cents
        existing.notes = notes
        if granted_by_user_id is not None:
            existing.granted_by_user_id = granted_by_user_id
        from datetime import datetime
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    new_row = CustomerFeature(
        customer_id=customer_id,
        feature_slug=slug,
        enabled=enabled,
        custom_price_cents=custom_price_cents,
        notes=notes,
        granted_by_user_id=granted_by_user_id,
    )
    session.add(new_row)
    session.commit()
    session.refresh(new_row)
    return new_row


def delete_customer_feature(
    session: Session, customer_id: int, slug: str,
) -> bool:
    """删除 override（回退到 registry 默认）。返回是否真的删除了。"""
    existing = _get_customer_override(session, customer_id, slug)
    if existing is None:
        return False
    session.delete(existing)
    session.commit()
    return True
