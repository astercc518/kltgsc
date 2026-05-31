from app.services.captcha_detector import detect_captcha_type


def test_no_captcha_when_no_messages():
    result = detect_captcha_type(recent_messages=[], admin_dms_after_join=[])
    assert result["type"] == "no_captcha"


def test_inline_button_detection():
    msg = {"text": "Click button to verify", "buttons": ["I am human"], "has_photo": False, "from_bot": True}
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "inline_button"


def test_text_qa_detection():
    msg = {"text": "你怎么知道这群的?", "buttons": [], "has_photo": False, "from_bot": True}
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "text_qa"


def test_vision_detection():
    msg = {"text": "请选择所有汽车", "buttons": [], "has_photo": True, "from_bot": True}
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "vision"


def test_admin_dm_detection():
    dm = {"text": "你为什么想加我们群?", "from_user_id": 5000}
    result = detect_captcha_type(recent_messages=[], admin_dms_after_join=[dm])
    assert result["type"] == "admin_dm"


def test_no_captcha_for_benign_human_chatter():
    """Phase 9: non-bot chatter without captcha vectors → no_captcha, not unknown."""
    msg = {"text": "Hello", "buttons": [], "has_photo": False, "from_bot": False}
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "no_captcha"


def test_unknown_when_bot_sends_uncategorised_message():
    """Bot-sent message that doesn't match any known captcha shape → unknown."""
    msg = {
        "text": "A long bot announcement without question marks or hints",
        "buttons": [], "has_photo": False, "from_bot": True,
    }
    result = detect_captcha_type(recent_messages=[msg], admin_dms_after_join=[])
    assert result["type"] == "unknown"
