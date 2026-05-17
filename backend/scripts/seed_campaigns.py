"""
种子脚本：创建战役 + 关联监控规则 + 关联脚本
7 个战役，覆盖海外市场精准引流各垂直场景
"""
import json
import sys
sys.path.insert(0, '/app')

from sqlmodel import Session, select
from app.core.db import engine
from app.models.campaign import Campaign
from app.models.keyword_monitor import KeywordMonitor
from app.models.ai_persona import AIPersona
from app.models.script import Script

# ─────────────────────────────────────────────────────────────
# 战役定义
# persona_name  → 主人设（用于 ai_persona_id）
# keywords      → 关联已有监控规则的关键词（设置 campaign_id）
# script_names  → 参考脚本（打印映射，目前 Campaign 模型无直接字段）
# ─────────────────────────────────────────────────────────────
CAMPAIGNS = [
    {
        "name": "🌏 出海私域引流·总战役",
        "description": (
            "面向有出海意向的华人群体，通过精准关键词拦截（出海获客/私域流量/社群裂变）"
            "自动触发 AI 人设老黄与欣姐互动，引导至私聊咨询，沉淀高质量线索。"
            "覆盖东南亚华人圈出海创业、私域运营、社群裂变全链路场景。"
        ),
        "status": "active",
        "allowed_roles": "cannon,actor,scout",
        "daily_budget": 500,
        "daily_account_limit": 50,
        "persona_name": "出海私域操盘手·老黄",
        "keywords": ["出海获客", "东南亚流量", "私域流量", "社群裂变", "出海创业"],
        "script_names": [
            "东南亚华人精准获客 · 流量焦虑讨论",
            "马来西亚华人市场 · 破圈进群实战",
            "出海华人获客 · 方法论对比大讨论",
        ],
    },
    {
        "name": "🛒 跨境电商爆品·选品战役",
        "description": (
            "瞄准跨境电商从业者/创业者群体，在[跨境电商][亚马逊选品][TikTok Shop]"
            "等话题中植入选品老炮建哥与青姐，输出蓝海选品方法论，"
            "带出东南亚华人私域选品情报库的价值，最终引流至私域社群。"
        ),
        "status": "active",
        "allowed_roles": "cannon,actor",
        "daily_budget": 300,
        "daily_account_limit": 30,
        "persona_name": "跨境电商·选品老炮",
        "keywords": ["跨境电商", "亚马逊选品", "TikTok Shop"],
        "script_names": ["跨境电商选品 · 蓝海 vs 红海争论"],
    },
    {
        "name": "💉 海外医美精准引流·战役",
        "description": (
            "面向东南亚（新马）定居华人女性群体，在医美相关话题中植入晴姐，"
            "用国内医美高性价比对比引发好奇，通过私聊转化为意向客户，"
            "最终引导飞回国内指定医美机构或线上平台消费。"
        ),
        "status": "active",
        "allowed_roles": "cannon,actor",
        "daily_budget": 200,
        "daily_account_limit": 20,
        "persona_name": "海外医美·获客顾问",
        "keywords": ["新加坡医美", "马来西亚医美", "水光针"],
        "script_names": ["海外医美获客 · 新加坡华人如何省钱做医美"],
    },
    {
        "name": "🎓 海外华人升学规划·战役",
        "description": (
            "面向东南亚（新马）华人家长群体，在子女升学/国际学校话题中植入吴老师，"
            "提供专业的升学路径分析（IGCSE/IB/A-Level），建立信任后引导预约"
            "免费升学规划咨询，转化为付费升学顾问服务客户。"
        ),
        "status": "active",
        "allowed_roles": "cannon,actor",
        "daily_budget": 150,
        "daily_account_limit": 15,
        "persona_name": "海外教育·华人升学顾问",
        "keywords": ["国际学校", "孩子升学"],
        "script_names": ["海外教育规划 · 华人家长的择校焦虑"],
    },
    {
        "name": "🏭 品牌出海·本地化战役",
        "description": (
            "面向有出海意向的国内品牌方和供应链企业，在品牌出海/东南亚建厂/跨境收款话题"
            "中植入宇哥（本地化专家）和强哥（供应链整合商），"
            "通过失败案例+解决方案的叙事结构，引出专业出海咨询和渠道对接服务。"
        ),
        "status": "active",
        "allowed_roles": "cannon,actor",
        "daily_budget": 200,
        "daily_account_limit": 20,
        "persona_name": "品牌出海·本地化专家",
        "keywords": ["品牌出海", "东南亚建厂", "跨境收款"],
        "script_names": [
            "品牌出海本地化 · 一家国内品牌的血泪教训",
            "海外供应链对接 · 国内工厂如何直连东南亚买家",
        ],
    },
    {
        "name": "🌐 Web3 华人社区·运营战役",
        "description": (
            "面向 Web3/加密/DeFi 圈子的华人用户，在项目讨论/跑路预警话题中植入"
            "Zhiyuan 等理性分析派人设，通过链上数据分析建立信任，"
            "引流至高质量华人 Web3 分析社区，为社区付费会员转化做铺垫。"
        ),
        "status": "active",
        "allowed_roles": "cannon,actor",
        "daily_budget": 150,
        "daily_account_limit": 15,
        "persona_name": "Web3·华人社区运营官",
        "keywords": ["Web3 社区", "项目跑路"],
        "script_names": ["Web3 华人社区 · 项目真假辨别"],
    },
    {
        "name": "🏠 海外房产投资·战役",
        "description": (
            "面向有海外资产配置需求的华人（国内高净值/已在海外的投资者），"
            "在海外买房/马来西亚置业话题中植入赵哥，提供专业的产权/税务/资金分析，"
            "通过「帮你避坑」的顾问姿态引导私聊，转化为房产咨询/看房意向客户。"
        ),
        "status": "active",
        "allowed_roles": "cannon,actor",
        "daily_budget": 100,
        "daily_account_limit": 10,
        "persona_name": "海外房产·华人投资顾问",
        "keywords": ["海外买房", "马来西亚置业"],
        "script_names": ["新加坡华人高净值客户 · 精准触达方案"],
    },
]


def run():
    with Session(engine) as session:
        # 构建查找 map
        all_personas = session.exec(select(AIPersona)).all()
        persona_map = {p.name: p.id for p in all_personas}

        all_rules = session.exec(select(KeywordMonitor)).all()
        rule_map = {r.keyword: r for r in all_rules}  # keyword -> rule obj

        all_scripts = session.exec(select(Script)).all()
        script_map = {s.name: s.id for s in all_scripts}

        created = []
        skipped = []

        for c in CAMPAIGNS:
            exists = session.exec(
                select(Campaign).where(Campaign.name == c["name"])
            ).first()
            if exists:
                skipped.append(c["name"])
                continue

            persona_id = persona_map.get(c["persona_name"])
            if not persona_id:
                print(f"  ⚠️  找不到人设 '{c['persona_name']}'，战役跳过")
                continue

            campaign = Campaign(
                name=c["name"],
                description=c["description"],
                status=c["status"],
                allowed_roles=c["allowed_roles"],
                daily_budget=c["daily_budget"],
                daily_account_limit=c["daily_account_limit"],
                ai_persona_id=persona_id,
            )
            session.add(campaign)
            session.flush()  # get campaign.id

            # 关联监控规则 → 设置 campaign_id
            rule_linked = []
            for kw in c.get("keywords", []):
                rule = rule_map.get(kw)
                if rule:
                    rule.campaign_id = campaign.id
                    session.add(rule)
                    rule_linked.append(kw)
                else:
                    print(f"  ⚠️  规则 '{kw}' 不存在，跳过关联")

            # 脚本映射（打印参考，Campaign 模型无直接字段）
            script_refs = []
            for sname in c.get("script_names", []):
                sid = script_map.get(sname)
                if sid:
                    script_refs.append(f"#{sid}")

            created.append({
                "name": c["name"],
                "id": campaign.id,
                "persona": c["persona_name"],
                "rules": rule_linked,
                "scripts": script_refs,
            })

        session.commit()

        print(f"✅ 新建战役 {len(created)} 个（跳过已存在 {len(skipped)} 个）\n")
        for camp in created:
            print(f"  [{camp['id']:2}] {camp['name']}")
            print(f"       主人设: {camp['persona']}")
            print(f"       监控规则: {', '.join(camp['rules']) or '无'}")
            print(f"       脚本参考: {', '.join(camp['scripts']) or '无'}")
            print()

        # 汇总
        total = len(session.exec(select(Campaign)).all())
        print(f"📊 战役总数: {total} 个")

        # 验证规则关联
        bound_rules = [r for r in session.exec(select(KeywordMonitor)).all() if r.campaign_id]
        unbound = [r for r in session.exec(select(KeywordMonitor)).all() if not r.campaign_id]
        print(f"   已关联战役的监控规则: {len(bound_rules)} 条")
        print(f"   未关联战役的监控规则: {len(unbound)} 条")
        if unbound:
            print(f"   未关联: {[r.keyword for r in unbound]}")


if __name__ == "__main__":
    run()
