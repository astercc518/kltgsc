"""seed_chitchat_pool: idempotent 写入内置话题, 已存在不重复"""
from unittest.mock import MagicMock, patch

from app.services.chitchat_pool_seeder import seed_chitchat_pool, GLOBAL_TOPICS


def test_global_topics_count_at_least_30():
    assert len(GLOBAL_TOPICS) >= 30


def test_seed_idempotent_skips_existing():
    fake_session = MagicMock()
    fake_session.exec.return_value.first.return_value = MagicMock(id=1)  # 已存在
    n_added = seed_chitchat_pool(session=fake_session)
    assert n_added == 0
    fake_session.add.assert_not_called()


def test_seed_inserts_when_missing():
    fake_session = MagicMock()
    fake_session.exec.return_value.first.return_value = None  # 不存在
    n_added = seed_chitchat_pool(session=fake_session)
    assert n_added == len(GLOBAL_TOPICS)
    assert fake_session.add.call_count == len(GLOBAL_TOPICS)
    fake_session.commit.assert_called()
