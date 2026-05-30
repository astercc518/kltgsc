"""Phase 6: 验证 listener + dispatcher 文件含 record_event 挂钩"""
import os

_HERE = os.path.dirname(__file__)
_SERVICES = os.path.join(_HERE, "..", "app", "services")


def test_listener_imports_record_event():
    path = os.path.join(_SERVICES, "listener_service.py")
    src = open(path).read()
    assert "from app.services.account_lifecycle_tracker import record_event" in src, \
        "listener_service.py must import record_event"
    assert 'event_type="session_invalid"' in src or "event_type='session_invalid'" in src, \
        "listener_service.py must record session_invalid event"


def test_dispatcher_imports_record_event():
    path = os.path.join(_SERVICES, "group_dispatcher.py")
    src = open(path).read()
    assert "from app.services.account_lifecycle_tracker import record_event" in src, \
        "group_dispatcher.py must import record_event"
    assert 'event_type="kicked_from_chat"' in src or "event_type='kicked_from_chat'" in src, \
        "group_dispatcher.py must record kicked_from_chat event"
