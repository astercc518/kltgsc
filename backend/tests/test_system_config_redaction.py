from app.models.system_config import SystemConfig


def _seed_config(session, key: str, value: str) -> None:
    session.add(SystemConfig(key=key, value=value, description=f"config {key}"))
    session.commit()


def test_config_list_redacts_sensitive_values(client, session) -> None:
    _seed_config(session, "OPENAI_API_KEY", "live-looking-api-key")
    _seed_config(session, "DEFAULT_TIMEZONE", "UTC")

    response = client.get("/api/v1/system/config")

    assert response.status_code == 200
    rows = {row["key"]: row for row in response.json()}
    assert rows["OPENAI_API_KEY"]["value"] is None
    assert rows["OPENAI_API_KEY"]["is_sensitive"] is True
    assert rows["OPENAI_API_KEY"]["is_configured"] is True
    assert rows["DEFAULT_TIMEZONE"]["value"] == "UTC"
    assert rows["DEFAULT_TIMEZONE"]["is_sensitive"] is False


def test_config_detail_redacts_sensitive_values(client, session) -> None:
    _seed_config(session, "NOWPAYMENTS_IPN_SECRET", "live-looking-ipn-secret")

    response = client.get("/api/v1/system/config/NOWPAYMENTS_IPN_SECRET")

    assert response.status_code == 200
    assert response.json()["value"] is None
    assert response.json()["is_configured"] is True


def test_config_write_does_not_echo_sensitive_value(client) -> None:
    response = client.post(
        "/api/v1/system/config",
        json={
            "key": "SERVICE_TOKEN",
            "value": "live-looking-service-token",
            "description": "service credential",
        },
    )

    assert response.status_code == 200
    assert response.json()["value"] is None
    assert response.json()["is_sensitive"] is True
    assert response.json()["is_configured"] is True
