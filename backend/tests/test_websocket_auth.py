from datetime import datetime, timedelta

import pytest
from jose import jwt

from app.api.v1.endpoints import ws
from app.core.config import settings
from app.models.user import USER_ROLE_ADMIN, USER_ROLE_SALES, User


def _token(
    *,
    subject: str = "admin",
    token_type: str | None = "access",
    jti: str | None = "test-jti",
    expires_at: datetime | None = None,
) -> str:
    payload: dict[str, object] = {
        "sub": subject,
        "exp": expires_at or datetime.utcnow() + timedelta(minutes=5),
    }
    if token_type is not None:
        payload["type"] = token_type
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _add_user(session, *, username: str, role: str, active: bool = True) -> User:
    user = User(
        username=username,
        hashed_password="unused-in-test",
        role=role,
        is_active=active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.mark.parametrize(
    "token",
    [
        None,
        "not-a-jwt",
        _token(expires_at=datetime.utcnow() - timedelta(seconds=1)),
        _token(jti=None),
        _token(token_type="customer"),
        _token(token_type="customer_sales"),
        _token(token_type="unexpected"),
    ],
)
def test_websocket_rejects_invalid_platform_credentials(session, monkeypatch, token) -> None:
    monkeypatch.setattr(ws, "is_token_revoked", lambda _jti: False, raising=False)

    with pytest.raises(ws.WebSocketAuthError):
        ws.authenticate_websocket_admin(token, session)


def test_websocket_rejects_revoked_token(session, monkeypatch) -> None:
    _add_user(session, username="revoked-admin", role=USER_ROLE_ADMIN)
    monkeypatch.setattr(ws, "is_token_revoked", lambda _jti: True, raising=False)

    with pytest.raises(ws.WebSocketAuthError) as exc_info:
        ws.authenticate_websocket_admin(
            _token(subject="revoked-admin", jti="revoked-jti"), session
        )

    assert exc_info.value.close_code == 4003


@pytest.mark.parametrize(
    ("username", "role", "active", "expected_code"),
    [
        ("missing", USER_ROLE_ADMIN, True, 4003),
        ("inactive", USER_ROLE_ADMIN, False, 4003),
        ("sales", USER_ROLE_SALES, True, 4004),
    ],
)
def test_websocket_rejects_non_admin_user_state(
    session, monkeypatch, username: str, role: str, active: bool, expected_code: int
) -> None:
    if username != "missing":
        _add_user(session, username=username, role=role, active=active)
    monkeypatch.setattr(ws, "is_token_revoked", lambda _jti: False, raising=False)

    with pytest.raises(ws.WebSocketAuthError) as exc_info:
        ws.authenticate_websocket_admin(_token(subject=username), session)

    assert exc_info.value.close_code == expected_code


def test_websocket_accepts_active_admin(session, monkeypatch) -> None:
    admin = _add_user(session, username="socket-admin", role=USER_ROLE_ADMIN)
    monkeypatch.setattr(ws, "is_token_revoked", lambda _jti: False, raising=False)

    authenticated = ws.authenticate_websocket_admin(
        _token(subject=admin.username, token_type=None), session
    )

    assert authenticated.id == admin.id


def test_admin_websocket_ping_pong(client, session, monkeypatch) -> None:
    admin = _add_user(session, username="ping-admin", role=USER_ROLE_ADMIN)
    monkeypatch.setattr(ws, "is_token_revoked", lambda _jti: False, raising=False)

    with client.websocket_connect(
        f"/api/v1/ws?token={_token(subject=admin.username)}"
    ) as socket:
        socket.send_text("ping")
        assert socket.receive_text() == "pong"
