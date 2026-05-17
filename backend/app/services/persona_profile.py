"""
从 AIPersona.system_prompt 中提取 TG 账号资料（姓名、简介）。

支持两种格式：
  A. 有 [人类档案] 块：解析 姓名/工作/爱好 字段
  B. 英文/无档案人设：从 [Role]/描述首句 + persona.name 推断

返回的字段直接可以传入 update_profile_with_client。
"""
import re
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 常见中文备用名池（当无法解析姓名时按 persona_id 种子随机取）
_SURNAMES = ["李", "王", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
             "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "郑"]
_FIRSTNAMES_2 = ["小明", "小红", "晓雨", "子轩", "雨萱", "浩然", "欣怡", "思远",
                 "嘉豪", "若冰", "宇轩", "梦琪", "泽宇", "雪儿", "志远", "婷婷",
                 "凌云", "海涛", "佳琪", "晨曦"]
_FIRSTNAMES_1 = ["芳", "伟", "强", "勇", "刚", "静", "华", "磊", "洋", "涛",
                 "敏", "军", "杰", "晶", "超", "宁", "峰", "琳", "波", "辉"]


def _random_chinese_name(seed: int) -> tuple[str, str]:
    """按 seed 生成一致的中文姓名，返回 (last_name, first_name)"""
    rng = random.Random(seed)
    surname = rng.choice(_SURNAMES)
    first = rng.choice(_FIRSTNAMES_2 if rng.random() > 0.4 else _FIRSTNAMES_1)
    return surname, first


def _parse_chinese_name(raw: str) -> tuple[str, str]:
    """
    解析姓名字符串，返回 (last_name, first_name)。
    'Mike Chen' → ('', 'Mike Chen')
    '七七（昵称…）' → ('', '七七')
    '李欣怡' → ('李', '欣怡')
    '阿凯（团队里叫凯哥）' → ('', '阿凯')
    """
    # 去掉括号及其内容（保留括号前的显示名）
    raw = raw.strip()
    bracket = re.match(r'^([^（\(（【\[]+)', raw)
    display = (bracket.group(1) if bracket else raw).strip()

    # 英文名（含空格或纯ASCII）：整体作为 first_name
    if re.match(r'^[A-Za-z\s\-\.]+$', display):
        parts = display.split()
        if len(parts) >= 2:
            return parts[-1], ' '.join(parts[:-1])  # last=surname, first=given
        return '', display

    # 纯中文：2字 → 整体first；3+字 → 首字last + 剩余first
    # 但昵称如"七七"、"阿凯"不要拆
    if len(display) == 2:
        return '', display
    if len(display) >= 3:
        return display[0], display[1:]
    return '', display


def extract_tg_profile(persona, seed_fallback: int = 0) -> dict:
    """
    从 AIPersona 对象提取 TG 账号资料。

    Returns:
        {
            "first_name": str,   # TG 名（最长64字）
            "last_name":  str,   # TG 姓（最长64字，可空）
            "about":      str,   # 简介/bio（最长70字）
        }
    """
    sp = persona.system_prompt or ""
    first_name = ""
    last_name = ""
    about = ""

    # ── 1. 解析姓名 ─────────────────────────────────────────────────────
    name_m = re.search(r'姓名[:：]\s*([^\n]{2,30})', sp)
    if name_m:
        last_name, first_name = _parse_chinese_name(name_m.group(1))
    else:
        # English persona: try [Name] or use persona.name first word
        eng_m = re.search(r'\[Name\]\s*([^\n]{2,30})', sp, re.IGNORECASE)
        if eng_m:
            last_name, first_name = _parse_chinese_name(eng_m.group(1))
        else:
            # 用人设名称第一个词/段
            raw_name = re.split(r'[·\s·\-]', persona.name)[0]
            if re.match(r'^[A-Za-z]', raw_name):
                first_name = raw_name
            else:
                # 给中文人设名称但无姓名字段时，随机生成
                last_name, first_name = _random_chinese_name(seed_fallback or (persona.id or 0))

    # ── 2. 生成简介 (about/bio, max 70 chars) ───────────────────────────
    job_m = re.search(r'(?:工作经历|职业|工作|职位)[:：]\s*([^\n]{4,50})', sp)
    hobby_m = re.search(r'爱好[:：]\s*([^\n]{4,40})', sp)
    role_line_m = re.search(r'\[(?:角色设定|Role)\]\s*\n(.{5,80})', sp)

    if job_m and hobby_m:
        job_part = job_m.group(1).split('，')[0].split(',')[0].strip()[:25]
        hobby_part = hobby_m.group(1).split('、')[0].split('/')[0].strip()[:20]
        about = f"{job_part}｜{hobby_part}"
    elif hobby_m:
        about = hobby_m.group(1).split('、')[0].strip()[:60]
    elif job_m:
        about = job_m.group(1).split('，')[0].strip()[:60]
    elif role_line_m:
        line = role_line_m.group(1).strip()
        # 截到第一个句号/换行
        sentence = re.split(r'[。！？\n]', line)[0]
        about = sentence[:60]
    elif persona.description:
        first_sent = re.split(r'[。！？\n]', persona.description)[0]
        about = first_sent[:60]

    return {
        "first_name": (first_name or persona.name[:10])[:64],
        "last_name": last_name[:64],
        "about": about[:70],
    }
