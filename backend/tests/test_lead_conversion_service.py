"""
lead_conversion_service — 查 source_user 在 sent 后 N 小时内私聊转化

Lead.telegram_user_id 是 source TG user 字段（由 lead.py 摸底确认）。
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.lead_conversion_service import (
    count_private_conversions_for_experiment,
)


def test_returns_zero_when_no_sent_rows():
    """没有 sent 行时返回 0，不报错"""
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = []
    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v1", window_hours=24,
    )
    assert cnt == 0


def test_returns_zero_when_no_lead_in_window():
    """有 sent 行，但 Lead 不在窗口内 → 返回 0"""
    now = datetime.now(timezone.utc)
    sent_rows = [(8888, now - timedelta(hours=3))]

    call_count = [0]

    def mock_exec(stmt):
        r = MagicMock()
        if call_count[0] == 0:
            # First call: sent rows query
            r.all.return_value = sent_rows
        else:
            # Subsequent calls: lead count query — no leads found
            r.first.return_value = 0
        call_count[0] += 1
        return r

    fake_session = MagicMock()
    fake_session.exec.side_effect = mock_exec

    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v1", window_hours=24,
    )
    assert cnt == 0


def test_counts_one_conversion_when_lead_exists_in_window():
    """1 个 sent 行 + Lead 在窗口内 → 返回 1"""
    now = datetime.now(timezone.utc)
    sent_rows = [(8888, now - timedelta(hours=3))]

    call_count = [0]

    def mock_exec(stmt):
        r = MagicMock()
        if call_count[0] == 0:
            r.all.return_value = sent_rows
        else:
            r.first.return_value = 1  # lead found
        call_count[0] += 1
        return r

    fake_session = MagicMock()
    fake_session.exec.side_effect = mock_exec

    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v1", window_hours=24,
    )
    assert cnt == 1


def test_counts_distinct_sent_rows_not_leads():
    """2 sent 行 (不同用户) 均有 Lead → 返回 2；不重复计"""
    now = datetime.now(timezone.utc)
    sent_rows = [
        (1001, now - timedelta(hours=2)),
        (1002, now - timedelta(hours=4)),
    ]

    call_count = [0]

    def mock_exec(stmt):
        r = MagicMock()
        if call_count[0] == 0:
            r.all.return_value = sent_rows
        else:
            r.first.return_value = 1  # each has a matching lead
        call_count[0] += 1
        return r

    fake_session = MagicMock()
    fake_session.exec.side_effect = mock_exec

    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v2", window_hours=24,
    )
    assert cnt == 2


def test_partial_conversions_mixed():
    """3 sent 行，只有 2 行的 Lead 在窗口内 → 返回 2"""
    now = datetime.now(timezone.utc)
    sent_rows = [
        (2001, now - timedelta(hours=1)),
        (2002, now - timedelta(hours=5)),
        (2003, now - timedelta(hours=10)),
    ]

    # lead_counts per row: [1, 0, 1]
    lead_counts = [1, 0, 1]
    call_count = [0]

    def mock_exec(stmt):
        r = MagicMock()
        if call_count[0] == 0:
            r.all.return_value = sent_rows
        else:
            idx = call_count[0] - 1  # 0-based index into lead_counts
            r.first.return_value = lead_counts[idx] if idx < len(lead_counts) else 0
        call_count[0] += 1
        return r

    fake_session = MagicMock()
    fake_session.exec.side_effect = mock_exec

    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v3", window_hours=24,
    )
    assert cnt == 2
