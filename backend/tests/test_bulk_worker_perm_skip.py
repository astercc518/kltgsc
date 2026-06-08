import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from app.models.bulk_send import (
    BulkBatch, BulkTarget, BulkTemplateVariant,
    BATCH_RUNNING, TARGET_PENDING, TARGET_SKIPPED, TARGET_FAILED,
)


@pytest.fixture
def mem_engine(monkeypatch):
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr("app.tasks.bulk_send_tasks.engine", eng)
    return eng


def _seed(eng, n):
    with Session(eng) as s:
        b = BulkBatch(customer_id=1, name="t", message_template="hi", status=BATCH_RUNNING,
                      min_delay_sec=0, max_delay_sec=0)
        s.add(b); s.flush()
        s.add(BulkTemplateVariant(batch_id=b.id, content="hi"))
        tids = []
        for i in range(n):
            t = BulkTarget(batch_id=b.id, customer_id=1, tg_username=f"u{i}", status=TARGET_PENDING)
            s.add(t); s.flush(); tids.append(t.id)
        s.commit()
        return b.id, tids


def test_permanent_failure_marks_skipped_not_failed(mem_engine, monkeypatch):
    from app.tasks import bulk_send_tasks as bt
    monkeypatch.setattr(bt, "mock_mode_enabled", lambda: False)
    monkeypatch.setattr(bt, "charge_for_target", lambda s, b, t: True)
    monkeypatch.setattr(bt, "pick_variant",
                        lambda s, bid: s.exec(select(BulkTemplateVariant).where(BulkTemplateVariant.batch_id == bid)).first())
    monkeypatch.setattr(bt, "mark_batch_completed_if_done", lambda s, b: None)
    monkeypatch.setattr(bt, "_do_send", lambda s, aid, t, v, mock: (False, "perm:privacy_restricted"))

    batch_id, tids = _seed(mem_engine, 2)
    bt.bulk_worker_task(None, 5, batch_id, tids)  # self=None (celery stubbed)

    with Session(mem_engine) as s:
        targets = s.exec(select(BulkTarget)).all()
        assert all(t.status == TARGET_SKIPPED for t in targets)
        assert all(t.failed_reason == "perm:privacy_restricted" for t in targets)
        b = s.get(BulkBatch, batch_id)
        assert b.skipped_count == 2
        assert b.failed_count == 0
        assert b.status == BATCH_RUNNING  # not paused: perm failures don't trip the burst breaker


def test_transient_failure_marks_failed_and_counts(mem_engine, monkeypatch):
    from app.tasks import bulk_send_tasks as bt
    monkeypatch.setattr(bt, "mock_mode_enabled", lambda: False)
    monkeypatch.setattr(bt, "charge_for_target", lambda s, b, t: True)
    monkeypatch.setattr(bt, "pick_variant",
                        lambda s, bid: s.exec(select(BulkTemplateVariant).where(BulkTemplateVariant.batch_id == bid)).first())
    monkeypatch.setattr(bt, "mark_batch_completed_if_done", lambda s, b: None)
    monkeypatch.setattr(bt, "_do_send", lambda s, aid, t, v, mock: (False, "Failed: network"))

    batch_id, tids = _seed(mem_engine, 1)
    bt.bulk_worker_task(None, 5, batch_id, tids)  # self=None (celery stubbed)

    with Session(mem_engine) as s:
        t = s.exec(select(BulkTarget)).first()
        assert t.status == TARGET_FAILED
        b = s.get(BulkBatch, batch_id)
        assert b.failed_count == 1 and b.skipped_count == 0
