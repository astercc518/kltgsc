import pytest
from fastapi import HTTPException
from jose import jwt

from app.api.deps import get_current_admin, get_current_user
from app.core.config import settings
from app.models.user import USER_ROLE_SALES, User


@pytest.fixture
def platform_sales_user() -> User:
    return User(
        id=42,
        username="platform-sales",
        hashed_password="unused-in-test",
        role=USER_ROLE_SALES,
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def sales_client(client, platform_sales_user):
    from app.main import app

    app.dependency_overrides.pop(get_current_admin, None)
    app.dependency_overrides[get_current_user] = lambda: platform_sales_user
    return client


@pytest.mark.parametrize(
    "path",
    ["/api/v1/accounts/", "/api/v1/system/config", "/api/v1/users/"],
)
def test_platform_sales_cannot_read_management_routes(sales_client, path: str) -> None:
    response = sales_client.get(path)

    assert response.status_code == 403
    assert response.json()["message"] == "Admin role required"


def test_platform_sales_can_still_read_own_profile(sales_client) -> None:
    response = sales_client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json()["username"] == "platform-sales"


def test_admin_retains_management_access(client) -> None:
    assert client.get("/api/v1/accounts/").status_code == 200
    assert client.get("/api/v1/system/config").status_code == 200


@pytest.mark.parametrize("token_type", ["customer", "customer_sales"])
def test_platform_dependency_rejects_tenant_token_types(
    session, token_type: str
) -> None:
    collision_user = User(
        username="shared-identity",
        hashed_password="unused-in-test",
        role=USER_ROLE_SALES,
    )
    session.add(collision_user)
    session.commit()
    token = jwt.encode(
        {"sub": collision_user.username, "type": token_type},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, session=session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not a platform access token"
