"""persona_rewriter: 按 persona 字段做轻量字符串变换 (无 LLM)"""
import random

from app.services.persona_rewriter import apply_persona


def _persona(**overrides):
    base = {
        "display_name": "x", "region": None, "occupation": None,
        "speaking_style": "casual", "catchphrases": [],
        "active_hours": {}, "daily_reply_quota": 5,
        "per_chat_daily_quota": 2, "per_chat_cooldown_minutes": 120,
        "daily_chitchat_quota": 0,
        "observation_window_seconds_range": [60, 900],
        "typing_delay_seconds_range": [30, 120],
        "source": "db",
    }
    base.update(overrides)
    return base


def test_formal_style_unchanged():
    """formal 风格不做改写"""
    persona = _persona(speaking_style="formal")
    out = apply_persona("我们提供 USDT 大额结算服务", persona, seed=1)
    assert out == "我们提供 USDT 大额结算服务"


def test_casual_style_adds_sentence_ending_particles():
    """casual: 句末偶尔加 哈/咯/嗯"""
    persona = _persona(speaking_style="casual")
    # 用 seed 控制概率, 多次跑保证至少 1 次命中加尾
    found_particle = False
    for s in range(50):
        out = apply_persona("USDT 大额结算", persona, seed=s)
        if any(p in out[-3:] for p in ["哈", "咯", "嗯"]):
            found_particle = True
            break
    assert found_particle


def test_catchphrase_inserted_with_probability():
    """30% 概率插入口头禅 (从 catchphrases 选一个)"""
    persona = _persona(catchphrases=["搞不好", "我跟你说"])
    found = False
    for s in range(50):
        out = apply_persona("USDT 大额结算 私聊", persona, seed=s)
        if any(cp in out for cp in ["搞不好", "我跟你说"]):
            found = True
            break
    assert found


def test_dialect_northeastern_word_replacement():
    """northeastern_dialect: 搞 → 整, 应该 → 得"""
    persona = _persona(speaking_style="northeastern_dialect")
    out = apply_persona("我们搞 USDT 应该没问题", persona, seed=0)
    assert "整" in out
    assert "得" in out


def test_length_safe_cap_80():
    """改写后超 80 字 → 截到最近句末"""
    persona = _persona(speaking_style="casual", catchphrases=["我跟你说啊嗯"])
    long_text = "USDT 大额场外结算服务 直接 T+0 到账, 上周帮客户跑了 100k 单笔, 案例已成。" * 3
    out = apply_persona(long_text, persona, seed=0)
    assert len(out) <= 80


def test_zero_input_returns_empty():
    persona = _persona()
    assert apply_persona("", persona, seed=0) == ""
    assert apply_persona(None, persona, seed=0) is None
