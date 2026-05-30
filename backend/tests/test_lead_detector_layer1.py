"""LeadDetector Layer 1 (keyword filter) 单元测试"""
from app.services.lead_detector import layer1_keyword_match


def test_layer1_include_any_hits():
    filters = {"include": ["USDT", "比特币"], "exclude": [], "mode": "any"}
    result = layer1_keyword_match("想买 100k USDT 一次", filters)
    assert result["pass"] is True
    assert result["matched"] == ["USDT"]


def test_layer1_include_any_misses():
    filters = {"include": ["USDT"], "exclude": [], "mode": "any"}
    result = layer1_keyword_match("今天天气真不错", filters)
    assert result["pass"] is False
    assert result["matched"] == []


def test_layer1_exclude_blocks():
    filters = {"include": ["USDT"], "exclude": ["免费"], "mode": "any"}
    result = layer1_keyword_match("USDT 免费教学", filters)
    assert result["pass"] is False
    assert "免费" in result.get("excluded", [])


def test_layer1_mode_all():
    filters = {"include": ["USDT", "求"], "exclude": [], "mode": "all"}
    assert layer1_keyword_match("求 USDT 渠道", filters)["pass"] is True
    assert layer1_keyword_match("有 USDT 卖", filters)["pass"] is False


def test_layer1_case_insensitive():
    filters = {"include": ["usdt"], "exclude": [], "mode": "any"}
    assert layer1_keyword_match("找 USDT 大户", filters)["pass"] is True


def test_layer1_fallback_to_legacy_keyword_field():
    """keyword_filters=None 时降级用旧 keyword 字段"""
    result = layer1_keyword_match(
        "找 USDT 大户", filters=None, legacy_keyword="USDT"
    )
    assert result["pass"] is True
    assert result["matched"] == ["USDT"]


def test_layer1_empty_filters_and_no_legacy():
    """全空 → 不通过 (不能默认全过)"""
    assert layer1_keyword_match("任何消息", filters=None, legacy_keyword=None)["pass"] is False
