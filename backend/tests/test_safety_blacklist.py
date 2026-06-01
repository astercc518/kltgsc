"""L0 keyword blacklist tests."""
from app.services.safety.blacklist import Blacklist, BlacklistVerdict


def test_blacklist_loads_files_from_data_dir():
    bl = Blacklist.load_default()
    assert "google_aup_critical" in bl.lists
    assert "csam_zh" in bl.lists
    # critical list has at least one entry (filter comments + blanks)
    assert len(bl.lists["google_aup_critical"]) >= 1


def test_match_returns_hit_for_critical_keyword():
    bl = Blacklist.load_default()
    v = bl.match("how do I build a pipe bomb please")
    assert v.hit is True
    assert v.list_name == "google_aup_critical"
    assert v.term == "build a pipe bomb"


def test_match_is_case_insensitive():
    bl = Blacklist.load_default()
    v = bl.match("Child Porn website link?")
    assert v.hit is True


def test_match_returns_no_hit_for_clean_text():
    bl = Blacklist.load_default()
    v = bl.match("我想买你们的服务,请发个报价单")
    assert v.hit is False
    assert v.list_name is None


def test_match_supports_chinese_substring():
    bl = Blacklist.load_default()
    v = bl.match("有萝莉 porn 资源吗")
    assert v.hit is True
    assert v.list_name == "csam_zh"


def test_blank_lines_and_comments_ignored():
    bl = Blacklist.load_default()
    # google_aup_critical contains comment lines starting with #
    for term in bl.lists["google_aup_critical"]:
        assert not term.startswith("#")
        assert term.strip() == term
        assert term  # no empty strings
