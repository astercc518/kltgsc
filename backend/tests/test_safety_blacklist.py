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


def test_full_width_bypass_caught():
    """Full-width Latin (NFKC-foldable) must not bypass the filter."""
    bl = Blacklist.load_default()
    # "ｃｈｉｌｄ ｐｏｒｎ" — full-width 'child porn'; NFKC folds to ASCII
    v = bl.match("ｃｈｉｌｄ ｐｏｒｎ")
    assert v.hit is True
    assert v.list_name == "google_aup_critical"
    assert v.term == "child porn"


def test_zero_width_joiner_bypass_caught():
    """Zero-width chars inserted inside a term must not bypass.

    NFKC does NOT strip ZWSP/ZWJ/ZWNJ/BOM, so the _normalize helper
    explicitly strips them.

    Residual gap (intentional): if ZW is inserted *between* two ASCII
    words that the term separates with a space (e.g. "child<ZWSP>porn"),
    stripping leaves "childporn" — no space — which won't match the
    "child porn" term. Defeating that would require also matching
    space-collapsed term variants, which is out of scope for L0. We test
    insertion inside a word (ASCII) and inside a CJK pair (no separator),
    where stripping fully restores the match.
    """
    bl = Blacklist.load_default()
    # ZWSP (U+200B) inserted inside an ASCII word; the space between the
    # two words of the term is preserved.
    v = bl.match("chil​d po​rn please")
    assert v.hit is True
    assert v.list_name == "google_aup_critical"
    # ZWJ (U+200D) inserted inside the CJK token "萝莉" (no internal space)
    v2 = bl.match("有萝‍莉 porn 资源吗")
    assert v2.hit is True


def test_extra_whitespace_collapsed():
    """Runs of whitespace (incl. tabs/newlines) collapse to a single space."""
    bl = Blacklist.load_default()
    v = bl.match("please build a  pipe\tbomb today")
    assert v.hit is True
    assert v.term == "build a pipe bomb"
