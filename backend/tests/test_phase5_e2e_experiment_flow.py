"""
Phase 5 E2E: 完整 A/B 实验生命周期
  create → sent (insert rows) → metrics → report

场景:
  1. Create ABExperiment with 2 variants, status='running'
  2. Insert 4 sent PendingReply rows with experiment_tag='e2e_phase5_test:v1'
  3. Insert 2 sent + 2 skipped_throttled PendingReply rows for v2
  4. aggregate_metrics_by_tag for each tag → verify counts
  5. build_experiment_report → verify variants + significance present

跳过条件: 无 Postgres（BigInteger PK + 真实 DB round-trip）
"""
import os
import pytest
from datetime import datetime, timezone
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.models.ab_experiment import ABExperiment

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------

_db_url = os.environ.get("DATABASE_URL", "")
_postgres = _db_url.startswith(("postgresql", "postgres"))

pytestmark = pytest.mark.skipif(
    not _postgres,
    reason="E2E lifecycle test requires Postgres (BigInteger PK unsupported in SQLite)",
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def e2e_exp_fixtures():
    """
    Spin up a fresh Postgres session, create the bare minimum FK-required rows
    (Customer, Account, KeywordMonitor), an ABExperiment, and 8 PendingReply
    rows split across v1 / v2.  Cleans up in FK-safe order after the test.
    """
    if not _postgres:
        pytest.skip("Postgres not available")

    from app.models.customer import Customer
    from app.models.account import Account
    from app.models.keyword_monitor import KeywordMonitor
    import app.models  # noqa — ensure all SQLModel tables are registered

    test_engine = create_engine(_db_url, pool_pre_ping=True)
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        # ----------------------------------------------------------------
        # 1. Create supporting rows (Customer / Account / KeywordMonitor)
        # ----------------------------------------------------------------
        customer = Customer(
            email="e2e_phase5_exp@test.local",
            hashed_password="not-a-real-hash",
            name="E2E Phase5 Exp Customer",
        )
        session.add(customer)
        session.commit()
        session.refresh(customer)

        account = Account(
            phone_number="+85288881111",
            session_string="",
            status="active",
            role="worker",
            customer_id=customer.id,
        )
        session.add(account)
        session.commit()
        session.refresh(account)

        monitor = KeywordMonitor(
            customer_id=customer.id,
            chat_id=-100111222,
            keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"},
        )
        session.add(monitor)
        session.commit()
        session.refresh(monitor)

        # ----------------------------------------------------------------
        # 2. Create ABExperiment with 2 variants, status='running'
        # ----------------------------------------------------------------
        exp = ABExperiment(
            name="e2e_phase5_test",
            scope="customer",
            scope_value=customer.id,
            variants=[
                {"tag": "v1", "weight": 0.5, "params": {"layer3_score": 60}},
                {"tag": "v2", "weight": 0.5, "params": {"layer3_score": 70}},
            ],
            status="running",
            primary_metric="reply_rate",
            started_at=datetime.now(timezone.utc),
        )
        session.add(exp)
        session.commit()
        session.refresh(exp)

        now = datetime.now(timezone.utc)

        # ----------------------------------------------------------------
        # 3a. Insert 4 sent rows for v1
        # ----------------------------------------------------------------
        v1_rows = []
        for i in range(4):
            pr = PendingReply(
                customer_id=customer.id,
                monitor_id=monitor.id,
                chat_id=-100111222,
                message_id=1000 + i,
                source_user_id=9000 + i,
                source_text=f"USDT 大额买入 {i}",
                status=PendingReplyStatus.SENT.value,
                experiment_tag="e2e_phase5_test:v1",
                reply_text="好的, 大额 OK",
                sent_at=now,
                created_at=now,
            )
            session.add(pr)
            v1_rows.append(pr)
        session.commit()
        for pr in v1_rows:
            session.refresh(pr)

        # ----------------------------------------------------------------
        # 3b. Insert 2 sent + 2 skipped_throttled rows for v2
        # ----------------------------------------------------------------
        v2_rows = []
        for i in range(2):
            pr_sent = PendingReply(
                customer_id=customer.id,
                monitor_id=monitor.id,
                chat_id=-100111222,
                message_id=2000 + i,
                source_user_id=9100 + i,
                source_text=f"USDT 中额 {i}",
                status=PendingReplyStatus.SENT.value,
                experiment_tag="e2e_phase5_test:v2",
                reply_text="好的",
                sent_at=now,
                created_at=now,
            )
            session.add(pr_sent)
            v2_rows.append(pr_sent)
        for i in range(2):
            pr_skip = PendingReply(
                customer_id=customer.id,
                monitor_id=monitor.id,
                chat_id=-100111222,
                message_id=3000 + i,
                source_user_id=9200 + i,
                source_text=f"USDT skip {i}",
                status=PendingReplyStatus.SKIPPED_THROTTLED.value,
                experiment_tag="e2e_phase5_test:v2",
                skip_reason="throttled",
                created_at=now,
            )
            session.add(pr_skip)
            v2_rows.append(pr_skip)
        session.commit()
        for pr in v2_rows:
            session.refresh(pr)

        yield session, exp, customer.id, monitor.id, test_engine

        # ----------------------------------------------------------------
        # Cleanup (FK-safe order)
        # ----------------------------------------------------------------
        for pr in v1_rows + v2_rows:
            obj = session.get(PendingReply, pr.id)
            if obj:
                session.delete(obj)
        session.commit()

        exp_obj = session.get(ABExperiment, exp.id)
        if exp_obj:
            session.delete(exp_obj)
        session.commit()

        monitor_obj = session.get(KeywordMonitor, monitor.id)
        if monitor_obj:
            session.delete(monitor_obj)
        session.commit()

        acc_obj = session.get(Account, account.id)
        if acc_obj:
            session.delete(acc_obj)
        session.commit()

        cust_obj = session.get(Customer, customer.id)
        if cust_obj:
            session.delete(cust_obj)
        session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_e2e_experiment_lifecycle(e2e_exp_fixtures):
    """
    Full A/B experiment lifecycle:
      - v1 tag: 4 sent → reply_rate = 4/4 = 1.0, anti_hallucination_failure_rate = 0
      - v2 tag: 2 sent + 2 skipped_throttled → reply_rate = 2/4 = 0.5
      - build_experiment_report → 2 variant blocks, significance block present
    """
    from app.services.experiment_metrics_service import aggregate_metrics_by_tag
    from app.services.experiment_report_service import build_experiment_report

    session, exp, customer_id, monitor_id, test_engine = e2e_exp_fixtures

    # ----------------------------------------------------------------
    # 4. aggregate_metrics_by_tag for each tag
    # ----------------------------------------------------------------
    mc_v1 = aggregate_metrics_by_tag(
        session=session, experiment_tag="e2e_phase5_test:v1"
    )
    assert mc_v1.sent == 4, f"v1 sent expected 4, got {mc_v1.sent}"
    assert mc_v1.suggested == 0
    assert mc_v1.skipped_total == 0
    assert mc_v1.failed == 0
    assert mc_v1.total_triggered == 4
    assert abs(mc_v1.reply_rate() - 1.0) < 1e-9
    assert mc_v1.anti_hallucination_failure_rate() == 0.0

    mc_v2 = aggregate_metrics_by_tag(
        session=session, experiment_tag="e2e_phase5_test:v2"
    )
    assert mc_v2.sent == 2, f"v2 sent expected 2, got {mc_v2.sent}"
    assert mc_v2.skipped_total == 2, f"v2 skipped_total expected 2, got {mc_v2.skipped_total}"
    assert mc_v2.total_triggered == 4
    assert abs(mc_v2.reply_rate() - 0.5) < 1e-9

    # ----------------------------------------------------------------
    # 5. build_experiment_report → variants + significance present
    # ----------------------------------------------------------------
    report = build_experiment_report(session=session, experiment=exp)

    assert report["experiment"] == "e2e_phase5_test"
    assert report["primary_metric"] == "reply_rate"

    variants = report["variants"]
    assert len(variants) == 2, f"expected 2 variant blocks, got {len(variants)}"

    # Variant blocks are keyed by tag
    tags_in_report = {v["tag"] for v in variants}
    assert "v1" in tags_in_report, f"v1 missing from report variants: {tags_in_report}"
    assert "v2" in tags_in_report, f"v2 missing from report variants: {tags_in_report}"

    # Each variant block must carry counters + metrics + ci
    for vblock in variants:
        assert "counters" in vblock, f"no counters in {vblock['tag']}"
        assert "metrics" in vblock, f"no metrics in {vblock['tag']}"
        assert "ci" in vblock, f"no ci in {vblock['tag']}"
        ci = vblock["ci"]
        for key in (
            "reply_rate_ci",
            "private_conversion_rate_ci",
            "kick_rate_ci",
            "anti_hallucination_failure_rate_ci",
        ):
            assert key in ci, f"{key} missing from ci block of {vblock['tag']}"
            lo, hi = ci[key]
            assert lo <= hi, f"CI inverted for {key} in {vblock['tag']}: [{lo}, {hi}]"

    # Significance block must be present (2 variants exist)
    sig = report["significance"]
    assert sig is not None, "significance block is None with 2 variants"
    assert "z_stat" in sig
    assert "p_value" in sig
    assert "significant" in sig
    # v1 reply_rate=1.0 vs v2 reply_rate=0.5 with n=4 each —
    # p_value may or may not be < 0.05 at n=4, but the block must be populated
    assert isinstance(sig["significant"], bool)
