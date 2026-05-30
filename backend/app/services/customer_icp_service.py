"""
customer_icp_service — 写客户 ICP 画像 + 自动 embedding。

调用方:
  - admin endpoint PUT /admin/group-ai/customers/{id}/icp (Task 7)
  - portal endpoint PUT /portal/group-ai/icp (Portal phase)
触发条件: icp_profile_text 变更时。
"""
import logging
from typing import Optional

from app.models.customer import Customer
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)


async def set_customer_icp_text_and_embed(
    *, session, customer_id: int, new_text: Optional[str],
) -> bool:
    """
    更新 customer.icp_profile_text + 同步 embedding。

    Args:
        session: SQLModel Session
        customer_id: 客户 ID
        new_text: 新的 ICP 文本, None/空 表示清空

    Returns:
        True 客户存在并已更新; False 客户不存在
    """
    customer = session.get(Customer, customer_id)
    if customer is None:
        logger.warning("set_customer_icp_text: customer %d not found", customer_id)
        return False

    cleaned = (new_text or "").strip()
    if not cleaned:
        customer.icp_profile_text = None
        customer.icp_profile_embedding = None
    else:
        customer.icp_profile_text = cleaned
        vec = await embed_text(session=session, text=cleaned)
        # 失败时 embedding 留 None, Layer 2 会自动降级跳过
        customer.icp_profile_embedding = vec
        if vec is None:
            logger.warning(
                "set_customer_icp_text: embedding generation failed for customer %d, "
                "text saved but Layer 2 disabled until manual re-embed",
                customer_id,
            )

    session.add(customer)
    session.commit()
    return True
