from app.services.bulk_send_service import classify_target_status
from app.models.bulk_send import TARGET_PENDING, TARGET_SKIPPED


def test_userid_only_is_no_handle():
    status, reason = classify_target_status({"tg_user_id": 123}, existing_uids=set())
    assert status == TARGET_SKIPPED and reason == "no_handle"


def test_username_is_pending():
    status, reason = classify_target_status({"tg_username": "bob"}, existing_uids=set())
    assert status == TARGET_PENDING and reason is None


def test_phone_is_pending():
    status, reason = classify_target_status({"phone": "+1555"}, existing_uids=set())
    assert status == TARGET_PENDING and reason is None


def test_cross_batch_dedup_takes_priority():
    status, reason = classify_target_status({"tg_user_id": 123}, existing_uids={123})
    assert status == TARGET_SKIPPED and reason == "dedup_cross_batch"


def test_userid_with_username_is_pending():
    status, reason = classify_target_status(
        {"tg_user_id": 123, "tg_username": "bob"}, existing_uids=set())
    assert status == TARGET_PENDING and reason is None
