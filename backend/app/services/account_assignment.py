"""
账号自动分配 Service

- balanced 策略：按 last_active 新鲜度 + 数量百分比，自动划分 listener/actor/cannon
- quota 策略：用户传具体数量
- 给 actor 类账号随机绑定 AI 人设

核心约束：
- preview 模式仅返回计划，不写库
- apply 模式才真正修改 Account 表
- 不主动覆盖已有 ai_persona_id 的账号（除非显式 force=True）
"""
import logging
import random
from typing import Optional, List, Dict
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.account import Account
from app.models.ai_persona import AIPersona

logger = logging.getLogger(__name__)


# 默认排除的 persona（纯客服/Bot 类，不适合作为炒群演员）
DEFAULT_EXCLUDED_PERSONAS = {28, 29}


def _get_persona_pool(
    session: Session,
    persona_pool: Optional[List[int]] = None,
) -> List[AIPersona]:
    """获取候选 AI 人设池"""
    if persona_pool:
        rows = session.exec(
            select(AIPersona).where(AIPersona.id.in_(persona_pool))
        ).all()
    else:
        rows = session.exec(select(AIPersona)).all()
        rows = [p for p in rows if p.id not in DEFAULT_EXCLUDED_PERSONAS]
    return list(rows)


def _sort_by_seniority(accounts: List[Account]) -> List[Account]:
    """按 last_active 升序：最早活跃的在前（适合做 listener，因为更老更稳）"""
    def key(a):
        if a.last_active is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        # Normalize naive datetimes to UTC for comparison
        if a.last_active.tzinfo is None:
            return a.last_active.replace(tzinfo=timezone.utc)
        return a.last_active
    return sorted(accounts, key=key)


def auto_assign(
    session: Session,
    account_ids: Optional[List[int]] = None,
    strategy: str = "balanced",
    quotas: Optional[Dict[str, int]] = None,
    persona_pool: Optional[List[int]] = None,
    preview: bool = True,
    force_persona: bool = False,
) -> Dict:
    """
    自动分配账号角色 + AI 人设。

    Args:
        session: 数据库 session
        account_ids: 待分配的账号 ID 列表，None 表示全部 active 账号
        strategy: "balanced" 或 "quota"
        quotas: strategy=quota 时必填: {"listener": 1, "actor": 5, "cannon": 14}
        persona_pool: 候选人设 ID 列表，None 用默认池（排除 28/29）
        preview: True 仅返回计划不写库；False 写库
        force_persona: True 时即使账号已有 persona 也会覆盖

    Returns:
        {
            "strategy": str,
            "total": int,
            "applied": bool,
            "plan": [
                {
                    "account_id": int,
                    "phone": str,
                    "tier": str,
                    "role": str,
                    "combat_role": str,
                    "ai_persona_id": int | None,
                    "persona_name": str | None,
                }
            ]
        }
    """
    # 1. 加载候选账号
    query = select(Account).where(Account.status == "active")
    if account_ids:
        query = query.where(Account.id.in_(account_ids))
    accounts = list(session.exec(query).all())

    if not accounts:
        return {"strategy": strategy, "total": 0, "applied": False, "plan": []}

    # 2. 加载人设池
    personas = _get_persona_pool(session, persona_pool)
    if not personas:
        logger.warning("Persona pool empty; actor accounts will not be bound")

    # 3. 决定每个分桶的数量
    total = len(accounts)
    if strategy == "quota":
        if not quotas:
            raise ValueError("strategy=quota requires `quotas` dict")
        n_listener = max(0, int(quotas.get("listener", 0)))
        n_actor = max(0, int(quotas.get("actor", 0)))
        n_cannon = max(0, total - n_listener - n_actor)
        if n_listener + n_actor > total:
            raise ValueError(
                f"quotas sum ({n_listener + n_actor}) exceeds total accounts ({total})"
            )
    elif strategy == "balanced":
        # 默认比例：5% listener（至少 1）, 25% actor（至少 2）, 余 cannon
        n_listener = max(1, int(round(total * 0.05)))
        n_actor = max(2, int(round(total * 0.25)))
        # 防越界
        if n_listener + n_actor > total:
            n_actor = max(0, total - n_listener)
        n_cannon = total - n_listener - n_actor
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")

    # 4. 排序：按 seniority（老号优先做 listener）
    sorted_accounts = _sort_by_seniority(accounts)

    plan = []
    persona_iter = iter(_round_robin(personas)) if personas else iter([])

    for idx, acct in enumerate(sorted_accounts):
        if idx < n_listener:
            tier = "tier1"
            role = "listener"
            combat = "scout"
            persona_id = None
            persona_name = None
        elif idx < n_listener + n_actor:
            tier = "tier2"
            role = "support"
            combat = "actor"
            # 绑定人设：优先保留已有的，除非 force
            if acct.ai_persona_id and not force_persona:
                persona_id = acct.ai_persona_id
                p = session.get(AIPersona, persona_id)
                persona_name = p.name if p else None
            else:
                p = next(persona_iter, None)
                persona_id = p.id if p else None
                persona_name = p.name if p else None
        else:
            tier = "tier3"
            role = "worker"
            combat = "cannon"
            persona_id = None
            persona_name = None

        plan.append({
            "account_id": acct.id,
            "phone": acct.phone_number,
            "tier": tier,
            "role": role,
            "combat_role": combat,
            "ai_persona_id": persona_id,
            "persona_name": persona_name,
        })

    # 5. 应用变更
    if not preview:
        for entry, acct in zip(plan, sorted_accounts):
            acct.tier = entry["tier"]
            acct.role = entry["role"]
            acct.combat_role = entry["combat_role"]
            # actor 才更新 persona；其他角色保持原值不动
            if entry["combat_role"] == "actor":
                acct.ai_persona_id = entry["ai_persona_id"]
            session.add(acct)
        session.commit()
        logger.info(f"auto_assign applied to {len(plan)} accounts (strategy={strategy})")

    return {
        "strategy": strategy,
        "total": total,
        "applied": not preview,
        "plan": plan,
    }


def _round_robin(items: List):
    """无限循环遍历列表（人设数 < 账号数时自动复用）"""
    if not items:
        return
    shuffled = list(items)
    random.shuffle(shuffled)
    while True:
        for item in shuffled:
            yield item


def auto_assign_imported(session: Session, account_ids: List[int]) -> int:
    """
    导入完成后的钩子：
    1. 设置 combat_role=cannon（未设置时）
    2. 随机绑定一个 AI 人设（未绑定时）
    3. 异步触发资料同步任务（写 TG 资料与人设匹配）

    幂等：已有 combat_role/ai_persona_id 的账号不覆盖。
    """
    if not account_ids:
        return 0

    accounts = session.exec(select(Account).where(Account.id.in_(account_ids))).all()
    personas = _get_persona_pool(session)  # 排除 FAQ/小蜜

    n = 0
    accounts_to_sync: List[tuple] = []  # (account_id, persona_id)

    for a in accounts:
        changed = False
        if a.combat_role is None:
            a.combat_role = "cannon"
            changed = True

        if a.ai_persona_id is None and personas:
            persona = random.choice(personas)
            a.ai_persona_id = persona.id
            changed = True
            accounts_to_sync.append((a.id, persona.id))
        elif a.ai_persona_id is not None:
            # 已有人设，也加入同步队列（幂等，任务内会检查）
            accounts_to_sync.append((a.id, a.ai_persona_id))

        if changed:
            session.add(a)
            n += 1

    if n:
        session.commit()

    # 延迟 30 秒触发资料同步，让 session 文件完全就绪
    if accounts_to_sync:
        try:
            from app.tasks.account_tasks import apply_persona_profile_task
            for account_id, persona_id in accounts_to_sync:
                apply_persona_profile_task.apply_async(
                    args=[account_id, persona_id],
                    countdown=30,
                )
        except Exception as e:
            logger.warning(f"Failed to queue profile sync tasks: {e}")

    return n


def assign_persona_to_account(
    session: Session,
    account_id: int,
    persona_id: Optional[int],
) -> Account:
    """单账号绑定/解绑 persona"""
    acct = session.get(Account, account_id)
    if not acct:
        raise ValueError(f"Account {account_id} not found")
    if persona_id is not None:
        persona = session.get(AIPersona, persona_id)
        if not persona:
            raise ValueError(f"AIPersona {persona_id} not found")
    acct.ai_persona_id = persona_id
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct


def batch_assign_persona(
    session: Session,
    account_ids: List[int],
    persona_id: int,
) -> int:
    """批量给一组账号绑定同一个 persona"""
    persona = session.get(AIPersona, persona_id)
    if not persona:
        raise ValueError(f"AIPersona {persona_id} not found")
    accounts = session.exec(select(Account).where(Account.id.in_(account_ids))).all()
    n = 0
    for a in accounts:
        a.ai_persona_id = persona_id
        session.add(a)
        n += 1
    session.commit()
    return n
