"""Layer 2: ICP embedding cosine 相似度匹配"""
from unittest.mock import patch, MagicMock

from app.services.lead_detector import layer2_icp_similarity


def test_layer2_passes_when_above_threshold():
    """模拟相似度 0.6 > 阈值 0.55 → PASS"""
    icp_vec = [1.0, 0.0, 0.0] + [0.0] * 765
    msg_vec = [0.9, 0.1, 0.0] + [0.0] * 765
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=msg_vec,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="求 USDT", icp_embedding=icp_vec,
            threshold=0.55,
        )
    assert result["pass"] is True
    assert result["similarity"] > 0.55


def test_layer2_blocks_below_threshold():
    """相似度 0.3 < 0.55 → block"""
    icp_vec = [1.0, 0.0] + [0.0] * 766
    msg_vec = [0.3, 0.95] + [0.0] * 766
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=msg_vec,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="今天天气", icp_embedding=icp_vec,
            threshold=0.55,
        )
    assert result["pass"] is False
    assert result["similarity"] < 0.55


def test_layer2_degrades_when_icp_embedding_missing():
    """customer.icp_profile_embedding=None → degrade pass (Layer 2 跳过)"""
    fake_session = MagicMock()
    result = layer2_icp_similarity(
        session=fake_session, text="任何", icp_embedding=None, threshold=0.55,
    )
    assert result["pass"] is True
    assert result["similarity"] is None
    assert result.get("degraded") is True


def test_layer2_degrades_when_message_embed_fails():
    """消息 embedding 服务挂 → degrade pass (不阻塞管线)"""
    icp_vec = [1.0] * 768
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=None,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="x", icp_embedding=icp_vec, threshold=0.55,
        )
    assert result["pass"] is True
    assert result["similarity"] is None
    assert result.get("degraded") is True


def test_layer2_borderline_flag():
    """边界值 (threshold-0.05 .. threshold) → pass=False 但 borderline=True"""
    import math
    icp_vec = [1.0, 0.0] + [0.0] * 766
    # 构造相似度 ≈ 0.52 (落在 [0.50, 0.55) 区间)
    angle = math.acos(0.52)
    msg_vec = [math.cos(angle), math.sin(angle)] + [0.0] * 766
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=msg_vec,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="x", icp_embedding=icp_vec, threshold=0.55,
        )
    assert result["pass"] is False
    assert result.get("borderline") is True
    assert 0.50 <= result["similarity"] < 0.55


def test_layer2_zero_vector_returns_zero_similarity():
    """全零向量边角 case: 相似度=0, 不 pass, 不 borderline"""
    icp_vec = [0.0] * 768
    msg_vec = [0.0] * 768
    fake_session = MagicMock()
    with patch(
        "app.services.lead_detector.embed_text", return_value=msg_vec,
    ):
        result = layer2_icp_similarity(
            session=fake_session, text="x", icp_embedding=icp_vec, threshold=0.55,
        )
    assert result["pass"] is False
    assert result["similarity"] == 0.0
