"""
Seed chitchat_pool 全局话题 (customer_id=NULL = 全部客户可用)。
Idempotent: 已存在的 prompt_template 不重复插入。

CLI: cd backend && python3 scripts/seed_chitchat_pool.py
"""
from typing import Optional
from sqlmodel import select


GLOBAL_TOPICS = [
    # weather (3)
    {"category": "weather", "template": "今天{城市}天气真闷, 出门要带伞", "tags": ["weather"]},
    {"category": "weather", "template": "最近降温太快, 大家都加衣服了", "tags": ["weather"]},
    {"category": "weather", "template": "雾霾天看大家都戴口罩, 自我防护", "tags": ["weather"]},
    # food (4)
    {"category": "food", "template": "外卖踩雷了, {菜名}居然没熟", "tags": ["food"]},
    {"category": "food", "template": "公司附近的{菜系}馆人均才 30, 性价比高", "tags": ["food"]},
    {"category": "food", "template": "周末打算去吃日料, 有推荐么", "tags": ["food"]},
    {"category": "food", "template": "刚做了顿西红柿炒蛋, 翻车了", "tags": ["food"]},
    # news (3)
    {"category": "news", "template": "看到{城市}通了新地铁线, 还挺方便", "tags": ["news"]},
    {"category": "news", "template": "最近油价又涨, 加一箱多花 50", "tags": ["news"]},
    {"category": "news", "template": "听说{影视剧}下周要播, 期待", "tags": ["news", "entertainment"]},
    # life (5)
    {"category": "life", "template": "周末搬家累成狗, 还是雇人靠谱", "tags": ["life"]},
    {"category": "life", "template": "我家猫又拆家, 抓狂", "tags": ["life", "pets"]},
    {"category": "life", "template": "刚下班路上堵了 40 分钟, 心累", "tags": ["life", "commute"]},
    {"category": "life", "template": "在家剪头发, 越剪越短", "tags": ["life"]},
    {"category": "life", "template": "新买的椅子坐着腰还是酸, 智商税", "tags": ["life"]},
    # tech (3)
    {"category": "tech", "template": "新手机续航不行, 一天三充", "tags": ["tech"]},
    {"category": "tech", "template": "Wi-Fi 又掉线, 重启路由器了", "tags": ["tech"]},
    {"category": "tech", "template": "PD 充电头一个能用就一直用", "tags": ["tech"]},
    # sports (3)
    {"category": "sports", "template": "昨天去打了一小时羽毛球, 浑身酸", "tags": ["sports"]},
    {"category": "sports", "template": "晨跑坚持了 3 天, 已经放弃了", "tags": ["sports"]},
    {"category": "sports", "template": "周末看球赛, 加时绝杀爽到", "tags": ["sports"]},
    # gossip (2)
    {"category": "gossip", "template": "公司新来的小哥发型很潮", "tags": ["gossip", "life"]},
    {"category": "gossip", "template": "邻居家半夜跳广场舞, 服了", "tags": ["gossip", "life"]},
    # work (3)
    {"category": "work", "template": "今天加班到 9 点, 头疼", "tags": ["work"]},
    {"category": "work", "template": "项目又改方向, 心累", "tags": ["work"]},
    {"category": "work", "template": "Boss 让我学新工具, 不会就完了", "tags": ["work"]},
    # travel (3)
    {"category": "travel", "template": "想趁假期去{城市}玩, 大家有推荐么", "tags": ["travel"]},
    {"category": "travel", "template": "高铁票越来越难抢, 怀念以前", "tags": ["travel"]},
    {"category": "travel", "template": "刚回来旅游一周, 累比上班还累", "tags": ["travel"]},
    # mood (3)
    {"category": "mood", "template": "今天心情奇好, 不知道为啥", "tags": ["mood"]},
    {"category": "mood", "template": "周一综合症晚期, 救救我", "tags": ["mood"]},
    {"category": "mood", "template": "感觉自己最近变懒了, 该健身了", "tags": ["mood"]},
]
# Total: 32 topics


def seed_chitchat_pool(*, session) -> int:
    """Idempotent: 返回新插入条数 (已存在的跳过)。"""
    from app.models.chitchat import ChitchatPool
    n_added = 0
    for item in GLOBAL_TOPICS:
        existing = session.exec(
            select(ChitchatPool).where(
                ChitchatPool.customer_id.is_(None),
                ChitchatPool.prompt_template == item["template"],
            )
        ).first()
        if existing is not None:
            continue
        row = ChitchatPool(
            customer_id=None,
            topic_category=item["category"],
            prompt_template=item["template"],
            tags=item["tags"],
            active=True,
        )
        session.add(row)
        n_added += 1
    if n_added > 0:
        session.commit()
    return n_added
