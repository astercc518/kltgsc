# 群发 username/phone Peer 解析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让群发支持 username / phone 目标的真实发送，并严格区分「目标级永久失败」与「账号级风控失败」，使客户自助群发对冷名单真正可用。

**Architecture:** 在 `telegram_client.py` 新增一个 peer 解析发送层 `resolve_and_send_with_client`（复用 `_create_client_and_run` 的客户端/代理/session 生命周期）：username 直接 `send_message`、phone 走 `import_contacts`→发→`delete_contacts`、裸 user_id 兜底。永久失败用 `perm:` 前缀回传，worker 据此把目标落 `skipped`（terminal、不重试、不惩罚账号），其余失败沿用现有 `failed`+熔断逻辑。创建批次时过滤掉「只有 user_id、无 username 无 phone」的不可达目标。

**Tech Stack:** Python 3, Pyrogram, SQLModel, Celery, pytest (mock pyrogram Client)。

参考 spec：`docs/superpowers/specs/2026-06-08-bulk-send-peer-resolution-design.md`

---

## File Structure

- `backend/app/services/telegram_client.py` — 新增 `_perm_code()`、`_send_with_typing()`、`resolve_and_send_with_client()`。
- `backend/app/tasks/bulk_send_tasks.py` — `_do_send()` 改调解析层；worker else 分支按 `perm:` 前缀分流到 `skipped`。
- `backend/app/services/bulk_send_service.py` — 创建批次持久化循环过滤 no_handle 目标。
- `backend/tests/test_bulk_peer_resolution.py` — 新建，覆盖解析层 8 项行为。
- `backend/tests/test_bulk_no_handle_filter.py` — 新建，覆盖创建期过滤。

无数据库迁移。

---

## Task 1: peer 错误码映射 `_perm_code`

**Files:**
- Modify: `backend/app/services/telegram_client.py`
- Test: `backend/tests/test_bulk_peer_resolution.py`

- [ ] **Step 1: Write the failing test**

新建 `backend/tests/test_bulk_peer_resolution.py`。文件顶部加一个 **autouse fixture 把解析层里的随机 sleep 归零**，否则 `_send_with_typing` 默认会真睡 3–8 秒拖慢测试：

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.telegram_client import _perm_code


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """让 _send_with_typing 的拟人化延迟在测试中瞬时完成。"""
    monkeypatch.setattr("app.services.telegram_client.random.uniform", lambda a, b: 0)
    async def _instant(*a, **kw):
        return None
    monkeypatch.setattr("app.services.telegram_client.asyncio.sleep", _instant)


def test_perm_code_maps_permanent_errors():
    assert _perm_code("Telegram says: [400 USERNAME_NOT_OCCUPIED]") == "username_not_occupied"
    assert _perm_code("USERNAME_INVALID") == "username_invalid"
    assert _perm_code("[400 PEER_ID_INVALID]") == "peer_id_invalid"
    assert _perm_code("USER_PRIVACY_RESTRICTED") == "privacy_restricted"
    assert _perm_code("PRIVACY_RESTRICTED whatever") == "privacy_restricted"


def test_perm_code_returns_none_for_transient():
    assert _perm_code("FLOOD_WAIT_X 30") is None
    assert _perm_code("Connection refused") is None
    assert _perm_code("PEER_FLOOD") is None
    assert _perm_code("") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -v`
Expected: FAIL with `ImportError: cannot import name '_perm_code'`

- [ ] **Step 3: Write minimal implementation**

在 `backend/app/services/telegram_client.py` 顶部（`logger = ...` 之后）新增：

```python
# 目标级永久失败错误码映射：这些错误是「目标本身」的问题，不应惩罚账号或重试。
_PERM_ERROR_MAP = (
    ("USERNAME_NOT_OCCUPIED", "username_not_occupied"),
    ("USERNAME_INVALID", "username_invalid"),
    ("USER_PRIVACY_RESTRICTED", "privacy_restricted"),
    ("PRIVACY_RESTRICTED", "privacy_restricted"),
    ("PEER_ID_INVALID", "peer_id_invalid"),
)


def _perm_code(error_str: str) -> Optional[str]:
    """把 Telegram 错误字符串映射为目标级永久失败码；瞬时/账号级返回 None。"""
    s = error_str or ""
    for needle, code in _PERM_ERROR_MAP:
        if needle in s:
            return code
    return None
```

注：`PRIVACY_RESTRICTED` 子串能同时匹配 `USER_PRIVACY_RESTRICTED`，元组顺序保证两者都归 `privacy_restricted`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/telegram_client.py backend/tests/test_bulk_peer_resolution.py
git commit -m "feat(bulk-send): add _perm_code permanent-error classifier"
```

---

## Task 2: 拟人化发送小工具 `_send_with_typing`

**Files:**
- Modify: `backend/app/services/telegram_client.py`
- Test: `backend/tests/test_bulk_peer_resolution.py`

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_bulk_peer_resolution.py`：

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.telegram_client import _send_with_typing


def test_send_with_typing_calls_send_message():
    client = MagicMock()
    client.send_chat_action = AsyncMock()
    client.send_message = AsyncMock()
    asyncio.run(_send_with_typing(client, "@bob", "hi", min_pre=0, max_pre=0, min_type=0, max_type=0))
    client.send_message.assert_awaited_once_with("@bob", "hi")


def test_send_with_typing_survives_typing_action_failure():
    client = MagicMock()
    client.send_chat_action = AsyncMock(side_effect=Exception("typing blocked"))
    client.send_message = AsyncMock()
    asyncio.run(_send_with_typing(client, 123, "hi", min_pre=0, max_pre=0, min_type=0, max_type=0))
    client.send_message.assert_awaited_once_with(123, "hi")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -k send_with_typing -v`
Expected: FAIL with `ImportError: cannot import name '_send_with_typing'`

- [ ] **Step 3: Write minimal implementation**

在 `telegram_client.py` 的 `_perm_code` 之后新增（镜像现有 `send_message_with_client` 186-192 的拟人化逻辑）：

```python
async def _send_with_typing(client, peer, message: str,
                            min_pre: float = 1.0, max_pre: float = 3.0,
                            min_type: float = 2.0, max_type: float = 5.0):
    """发送前模拟「在线→输入中→发送」，typing 动作失败不影响发送。"""
    await asyncio.sleep(random.uniform(min_pre, max_pre))
    try:
        await client.send_chat_action(peer, enums.ChatAction.TYPING)
        await asyncio.sleep(random.uniform(min_type, max_type))
    except Exception:
        pass
    await client.send_message(peer, message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -k send_with_typing -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/telegram_client.py backend/tests/test_bulk_peer_resolution.py
git commit -m "feat(bulk-send): add _send_with_typing humanized send helper"
```

---

## Task 3: 解析发送层 `resolve_and_send_with_client` — username 路径

**Files:**
- Modify: `backend/app/services/telegram_client.py`
- Test: `backend/tests/test_bulk_peer_resolution.py`

**说明：** 该函数复用现有 `_create_client_and_run(account, op, db_session=...)`。`op(client)` 返回 `("ok", None)` 或 `("perm", code)`；`_create_client_and_run` 成功时回 `(True, op返回值)`，对 FloodWait/PeerFlood/Banned 会设置 cooldown 并抛 `AccountException`，对其他异常回 `(False, "错误串")`。`resolve_and_send_with_client` 把这些统一翻译成 `(ok: bool, err: str|None)`，永久失败用 `perm:` 前缀。

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_bulk_peer_resolution.py`：

```python
from unittest.mock import patch
from app.services.telegram_client import resolve_and_send_with_client


def _fake_run(monkeypatch_target="app.services.telegram_client._create_client_and_run"):
    return monkeypatch_target


def test_username_send_success():
    async def fake_run(account, op, *a, **kw):
        client = MagicMock()
        client.send_chat_action = AsyncMock()
        client.send_message = AsyncMock()
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username="bob", phone=None,
            message="hi", db_session=None))
    assert ok is True and err is None


def test_username_not_occupied_is_permanent():
    async def fake_run(account, op, *a, **kw):
        client = MagicMock()
        client.send_chat_action = AsyncMock()
        client.send_message = AsyncMock(side_effect=Exception("[400 USERNAME_NOT_OCCUPIED]"))
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username="ghost", phone=None,
            message="hi", db_session=None))
    assert ok is False and err == "perm:username_not_occupied"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -k username -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_and_send_with_client'`

- [ ] **Step 3: Write minimal implementation**

在 `telegram_client.py` 的 `send_message_with_client` 之后新增（先只实现 username + user_id 兜底，phone 在 Task 4 补）：

```python
async def resolve_and_send_with_client(
    account: Account, *, tg_user_id, tg_username, phone,
    message: str, db_session: Optional[Session] = None,
) -> Tuple[bool, Optional[str]]:
    """按 username > phone > user_id 优先级解析并发送。
    返回 (ok, err)。err 以 'perm:' 开头表示目标级永久失败（不应惩罚账号/重试）。
    """
    async def op(client):
        # 1) username：Pyrogram 实时解析
        if tg_username:
            peer = tg_username if str(tg_username).startswith("@") else "@" + str(tg_username)
            try:
                await _send_with_typing(client, peer, message)
                return ("ok", None)
            except Exception as e:
                code = _perm_code(str(e))
                if code:
                    return ("perm", code)
                raise
        # 2) phone：Task 4 实现
        if phone:
            return await _send_via_phone(client, phone, message)
        # 3) 裸 user_id 兜底（号池冷发多半 PEER_ID_INVALID）
        if tg_user_id:
            try:
                await _send_with_typing(client, int(tg_user_id), message)
                return ("ok", None)
            except Exception as e:
                code = _perm_code(str(e))
                if code:
                    return ("perm", code)
                raise
        return ("perm", "no_handle")

    try:
        ok, result = await _create_client_and_run(account, op, db_session=db_session)
    except AccountException as e:
        # 账号级（flood/banned）：cooldown 已在 _create_client_and_run 内设置
        return False, str(e)[:200]
    if not ok:
        return False, str(result)[:200]
    kind, code = result
    if kind == "ok":
        return True, None
    return False, f"perm:{code}"
```

注意：`_send_via_phone` 在 Task 4 定义；本任务为让 username 测试通过，先补一个占位以避免 NameError（Task 4 替换）：

```python
async def _send_via_phone(client, phone, message):
    return ("perm", "phone_not_on_telegram")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -k username -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/telegram_client.py backend/tests/test_bulk_peer_resolution.py
git commit -m "feat(bulk-send): resolve_and_send_with_client username path"
```

---

## Task 4: phone 路径 `_send_via_phone`（import_contacts → 发 → delete_contacts）

**Files:**
- Modify: `backend/app/services/telegram_client.py`
- Test: `backend/tests/test_bulk_peer_resolution.py`

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_bulk_peer_resolution.py`：

```python
def _client_with_imported(users):
    client = MagicMock()
    client.send_chat_action = AsyncMock()
    client.send_message = AsyncMock()
    client.delete_contacts = AsyncMock()
    imported = MagicMock()
    imported.users = users
    client.import_contacts = AsyncMock(return_value=imported)
    return client


def test_phone_hit_sends_and_cleans_contact():
    user = MagicMock(); user.id = 555
    client = _client_with_imported([user])
    async def fake_run(account, op, *a, **kw):
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username=None, phone="+15551234567",
            message="hi", db_session=None))
    assert ok is True and err is None
    client.send_message.assert_awaited_once_with(555, "hi")
    client.delete_contacts.assert_awaited_once_with([555])


def test_phone_not_on_telegram_is_permanent():
    client = _client_with_imported([])
    async def fake_run(account, op, *a, **kw):
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username=None, phone="+15550000000",
            message="hi", db_session=None))
    assert ok is False and err == "perm:phone_not_on_telegram"


def test_phone_send_failure_still_cleans_contact():
    user = MagicMock(); user.id = 777
    client = _client_with_imported([user])
    client.send_message = AsyncMock(side_effect=Exception("USER_PRIVACY_RESTRICTED"))
    async def fake_run(account, op, *a, **kw):
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username=None, phone="+15557654321",
            message="hi", db_session=None))
    assert ok is False and err == "perm:privacy_restricted"
    client.delete_contacts.assert_awaited_once_with([777])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -k phone -v`
Expected: FAIL（占位 `_send_via_phone` 总回 phone_not_on_telegram，故 hit/failure 两例失败）

- [ ] **Step 3: Write minimal implementation**

在 `telegram_client.py` 顶部 import 区追加：

```python
from pyrogram.types import InputPhoneContact
```

用真正实现替换 Task 3 的占位 `_send_via_phone`：

```python
async def _send_via_phone(client, phone: str, message: str):
    """import_contacts 解析手机号→发→delete_contacts 清理。返回 ('ok',None)|('perm',code)。"""
    imported = await client.import_contacts(
        [InputPhoneContact(phone=str(phone), first_name="Contact")]
    )
    users = getattr(imported, "users", None) or []
    if not users:
        return ("perm", "phone_not_on_telegram")
    uid = users[0].id
    try:
        try:
            await _send_with_typing(client, uid, message)
            return ("ok", None)
        except Exception as e:
            code = _perm_code(str(e))
            if code:
                return ("perm", code)
            raise
    finally:
        try:
            await client.delete_contacts([uid])
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -v`
Expected: PASS（全部，含 username + phone + helpers）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/telegram_client.py backend/tests/test_bulk_peer_resolution.py
git commit -m "feat(bulk-send): phone path via import_contacts with contact cleanup"
```

---

## Task 5: `_do_send` 改用解析层

**Files:**
- Modify: `backend/app/tasks/bulk_send_tasks.py:263-301`
- Test: `backend/tests/test_bulk_peer_resolution.py`

- [ ] **Step 1: Write the failing test**

追加到 `backend/tests/test_bulk_peer_resolution.py`：

```python
from app.tasks.bulk_send_tasks import _do_send
from app.models.bulk_send import BulkTarget, BulkTemplateVariant


def test_do_send_prefers_username_over_userid(monkeypatch):
    captured = {}

    async def fake_resolve(account, *, tg_user_id, tg_username, phone, message, db_session):
        captured.update(tg_user_id=tg_user_id, tg_username=tg_username, phone=phone)
        return True, None

    monkeypatch.setattr(
        "app.services.telegram_client.resolve_and_send_with_client", fake_resolve
    )
    # account_id 用真实路径需 Account 存在；此处直接 mock session.get 返回一个对象
    fake_session = MagicMock()
    fake_session.get.return_value = MagicMock()  # account
    target = BulkTarget(batch_id=1, customer_id=1, tg_user_id=999, tg_username="bob")
    variant = BulkTemplateVariant(batch_id=1, content="hi")
    ok, err = _do_send(fake_session, account_id=5, target=target, variant=variant, mock=False)
    assert ok is True and err is None
    assert captured["tg_username"] == "bob" and captured["tg_user_id"] == 999


def test_do_send_passes_perm_error_through(monkeypatch):
    async def fake_resolve(account, **kw):
        return False, "perm:privacy_restricted"
    monkeypatch.setattr(
        "app.services.telegram_client.resolve_and_send_with_client", fake_resolve
    )
    fake_session = MagicMock()
    fake_session.get.return_value = MagicMock()
    target = BulkTarget(batch_id=1, customer_id=1, tg_username="bob")
    variant = BulkTemplateVariant(batch_id=1, content="hi")
    ok, err = _do_send(fake_session, account_id=5, target=target, variant=variant, mock=False)
    assert ok is False and err == "perm:privacy_restricted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -k do_send -v`
Expected: FAIL（现 `_do_send` 因 target 无 tg_user_id 在第二例返回 `real_send_needs_tg_user_id_in_mvp`；第一例调用的是旧 `send_message_with_client`，captured 不被填充）

- [ ] **Step 3: Write minimal implementation**

把 `backend/app/tasks/bulk_send_tasks.py` 的 `_do_send` real-send 段（第 282-301 行）替换为：

```python
    # Real send: 解析层按 username > phone > user_id 优先级发送
    if not (target.tg_user_id or target.tg_username or target.phone):
        return False, "no_handle"

    account = session.get(Account, account_id)
    if not account:
        return False, "account_missing"

    try:
        import asyncio
        from app.services.telegram_client import resolve_and_send_with_client
        ok, err = asyncio.run(
            resolve_and_send_with_client(
                account,
                tg_user_id=target.tg_user_id,
                tg_username=target.tg_username,
                phone=target.phone,
                message=variant.content,
                db_session=session,
            )
        )
        return bool(ok), (None if ok else err)
    except Exception as e:  # broad — Pyrogram raises many exception types
        return False, str(e)[:200]
```

同时更新 docstring（270-276 行）去掉「only supports tg_user_id」的过时描述，改为「按 username>phone>user_id 解析；perm: 前缀表目标级永久失败」。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py -k do_send -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/bulk_send_tasks.py backend/tests/test_bulk_peer_resolution.py
git commit -m "feat(bulk-send): _do_send routes through peer resolution layer"
```

---

## Task 6: worker 按 `perm:` 前缀把永久失败落 `skipped`

**Files:**
- Modify: `backend/app/tasks/bulk_send_tasks.py:25-29`（import）, `:196-208`（else 分支）
- Test: `backend/tests/test_bulk_worker_perm_skip.py`

- [ ] **Step 1: Write the failing test**

新建 `backend/tests/test_bulk_worker_perm_skip.py`（用 in-memory sqlite + 真实 worker 逻辑，mock `_do_send` 与账号选择）。

**两个环境要点（conftest 决定）：**
1. **必须用 `StaticPool`**——`sqlite://` 默认每个连接是独立内存库，worker 每个目标都开新 `Session(engine)`，不用 StaticPool 会读不到 seed 数据。
2. **celery 被 stub**，`@celery_app.task` 返回的就是原始函数（首参仍是 `self`），没有 `.delay/.run/.apply` 的真实行为。直接当普通函数调用并显式传 `self=None`：`bulk_worker_task(None, account_id, batch_id, tids)`。

```python
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


def _seed(eng, send_results):
    """send_results: list of (ok, err) returned by _do_send in order."""
    with Session(eng) as s:
        b = BulkBatch(customer_id=1, name="t", message_template="hi", status=BATCH_RUNNING,
                      min_delay_sec=0, max_delay_sec=0)
        s.add(b); s.flush()
        s.add(BulkTemplateVariant(batch_id=b.id, content="hi"))
        tids = []
        for i in range(len(send_results)):
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
    # 两个目标都永久失败
    monkeypatch.setattr(bt, "_do_send", lambda s, aid, t, v, mock: (False, "perm:privacy_restricted"))

    batch_id, tids = _seed(mem_engine, [(False, "perm")] * 2)
    bt.bulk_worker_task(None, 5, batch_id, tids)  # self=None (celery stubbed)

    with Session(mem_engine) as s:
        targets = s.exec(select(BulkTarget)).all()
        assert all(t.status == TARGET_SKIPPED for t in targets)
        assert all(t.failed_reason == "perm:privacy_restricted" for t in targets)
        b = s.get(BulkBatch, batch_id)
        assert b.skipped_count == 2
        assert b.failed_count == 0
        # 永久失败不触发熔断 → 批次未被暂停
        assert b.status == BATCH_RUNNING


def test_transient_failure_marks_failed_and_counts(mem_engine, monkeypatch):
    from app.tasks import bulk_send_tasks as bt
    monkeypatch.setattr(bt, "mock_mode_enabled", lambda: False)
    monkeypatch.setattr(bt, "charge_for_target", lambda s, b, t: True)
    monkeypatch.setattr(bt, "pick_variant",
                        lambda s, bid: s.exec(select(BulkTemplateVariant).where(BulkTemplateVariant.batch_id == bid)).first())
    monkeypatch.setattr(bt, "mark_batch_completed_if_done", lambda s, b: None)
    monkeypatch.setattr(bt, "_do_send", lambda s, aid, t, v, mock: (False, "Failed: network"))

    batch_id, tids = _seed(mem_engine, [(False, "x")])
    bt.bulk_worker_task(None, 5, batch_id, tids)  # self=None (celery stubbed)

    with Session(mem_engine) as s:
        t = s.exec(select(BulkTarget)).first()
        assert t.status == TARGET_FAILED
        b = s.get(BulkBatch, batch_id)
        assert b.failed_count == 1 and b.skipped_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_worker_perm_skip.py -v`
Expected: FAIL（当前 worker 把 perm 也当作 FAILED：`test_permanent_failure...` 断言 skipped/skipped_count 失败）

- [ ] **Step 3: Write minimal implementation**

(a) 在 `bulk_send_tasks.py` import 块（25-29 行）加入 `TARGET_SKIPPED`：

```python
from app.models.bulk_send import (
    BulkBatch, BulkTarget, BulkTemplateVariant,
    BATCH_PENDING, BATCH_RUNNING, BATCH_PAUSED, BATCH_COMPLETED, BATCH_FAILED,
    TARGET_PENDING, TARGET_SENDING, TARGET_SENT, TARGET_FAILED, TARGET_SKIPPED,
)
```

(b) 把 worker 的 else 分支（196-207 行）替换为：

```python
            else:
                is_permanent = bool(send_err) and send_err.startswith("perm:")
                if is_permanent:
                    # 目标级永久失败：落 skipped（terminal，dispatcher 不重拾），
                    # 不计 failed_count、不增连续失败（不惩罚账号、不触发熔断）。
                    target.status = TARGET_SKIPPED
                    target.failed_reason = send_err[:200]
                    s.add(target)
                    batch.skipped_count = (batch.skipped_count or 0) + 1
                    batch.updated_at = datetime.utcnow()
                    s.add(batch)
                    s.commit()
                    failed += 1  # 仍计入本 shard processed 统计（非熔断计数）
                else:
                    target.status = TARGET_FAILED
                    target.failed_reason = (send_err or "send_failed")[:200]
                    s.add(target)
                    batch.failed_count = (batch.failed_count or 0) + 1
                    batch.updated_at = datetime.utcnow()
                    s.add(batch)
                    s.commit()
                    failed += 1
                    consecutive_failures += 1
```

注意：`consecutive_failures += 1` 只在非永久失败分支执行——这是「不触发熔断」的关键。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_worker_perm_skip.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/bulk_send_tasks.py backend/tests/test_bulk_worker_perm_skip.py
git commit -m "feat(bulk-send): route perm: failures to skipped, spare account from burst"
```

---

## Task 7: 创建批次时过滤 no_handle 目标

**Files:**
- Modify: `backend/app/services/bulk_send_service.py:348-374`
- Test: `backend/tests/test_bulk_no_handle_filter.py`

- [ ] **Step 1: Write the failing test**

新建 `backend/tests/test_bulk_no_handle_filter.py`。该测试针对持久化循环：构造 `parsed` 行、断言只有 user_id 的行落 `skipped:no_handle`。因创建函数依赖 customer/wallet，这里直接测「持久化分类」的纯逻辑——把循环抽成可单测的辅助函数 `classify_target_status(row, existing_uids)`。

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_no_handle_filter.py -v`
Expected: FAIL with `ImportError: cannot import name 'classify_target_status'`

- [ ] **Step 3: Write minimal implementation**

(a) 在 `bulk_send_service.py` 新增辅助函数（放在 `create_batch_*` 函数上方）：

```python
def classify_target_status(row: dict, existing_uids: set) -> tuple[str, Optional[str]]:
    """决定单个目标落库状态。
    - 跨批次已存在 user_id → skipped:dedup_cross_batch（优先级最高）
    - 只有 user_id、无 username 无 phone → skipped:no_handle（号池冷发不可达）
    - 否则 → pending
    """
    uid = row.get("tg_user_id")
    if uid and uid in existing_uids:
        return TARGET_SKIPPED, "dedup_cross_batch"
    if uid and not row.get("tg_username") and not row.get("phone"):
        return TARGET_SKIPPED, "no_handle"
    return TARGET_PENDING, None
```

(b) 把持久化循环（348-368 行）替换为使用它，并分别累计两类 skip：

```python
    skipped_dedup = 0
    skipped_no_handle = 0
    for row in parsed:
        status, reason = classify_target_status(row, existing_uids)
        if reason == "dedup_cross_batch":
            skipped_dedup += 1
        elif reason == "no_handle":
            skipped_no_handle += 1
        session.add(BulkTarget(
            batch_id=batch.id,
            customer_id=customer.id,
            tg_user_id=row.get("tg_user_id"),
            tg_username=row.get("tg_username"),
            phone=row.get("phone"),
            display_name=row.get("display_name"),
            country=row.get("country"),
            extra_json=row.get("extra_json"),
            status=status,
            failed_reason=reason,
        ))

    batch.skipped_count = skipped_dedup + skipped_no_handle
```

(c) 在返回 summary 前补充计数（373 行附近）：

```python
    parse_summary["skipped_dedup_cross_batch"] = skipped_dedup
    parse_summary["skipped_no_handle"] = skipped_no_handle
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_no_handle_filter.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bulk_send_service.py backend/tests/test_bulk_no_handle_filter.py
git commit -m "feat(bulk-send): skip user_id-only targets as no_handle at batch creation"
```

---

## Task 8: 全量回归 + mock 路径未破坏验证

**Files:**
- Test: 既有 bulk 相关测试

- [ ] **Step 1: 跑解析层 + worker + 过滤新测试**

Run: `cd /var/tgsc/backend && python3 -m pytest tests/test_bulk_peer_resolution.py tests/test_bulk_worker_perm_skip.py tests/test_bulk_no_handle_filter.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 跑全量测试套件（回归，确认改动未破坏既有 import/模型/计费）**

说明：仓库当前 `backend/tests/` 无既有 bulk 专项测试，本计划新增的 3 个文件即首批；全量跑是为确认对 `telegram_client.py`/`bulk_send_service.py`/`bulk_send_tasks.py` 的改动不破坏其它模块（这些文件被多处 import）。

Run: `cd /var/tgsc/backend && python3 -m pytest -q`
Expected: 全部 PASS（基线 17+ 既有用例 + 本计划新增用例）

- [ ] **Step 3: 若有失败，按 systematic-debugging 处理后重跑；全绿后提交收尾（如有未提交改动）**

```bash
git add -A && git commit -m "test(bulk-send): peer resolution regression green" || echo "nothing to commit"
```

---

## Self-Review 结果

- **Spec 覆盖**：①username 发送 → Task 3；②phone import/delete → Task 4；③错误分类 perm vs 账号级 → Task 1+3+4（perm 码）+ Task 6（worker 分流）；④no_handle 创建期过滤 → Task 7；⑤不动 mock 路径 → Task 8 回归保护；⑥无迁移 → 全程未改 schema。✅ 无遗漏。
- **占位符扫描**：无 TBD/TODO；每个 code step 均给出完整代码与命令。✅
- **类型一致性**：`resolve_and_send_with_client(account, *, tg_user_id, tg_username, phone, message, db_session)` 在 Task 3 定义、Task 5 按同签名调用；`_send_via_phone` Task 3 占位 → Task 4 同名替换；`_perm_code`/`_send_with_typing`/`classify_target_status` 签名前后一致；`perm:` 前缀约定贯穿 Task 1/3/4/6。✅
