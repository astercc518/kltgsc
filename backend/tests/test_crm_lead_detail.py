from sqlmodel import Session

from app.models.lead import Lead, LeadInteraction


def test_lead_detail_includes_ordered_interactions(client, session: Session) -> None:
    lead = Lead(telegram_user_id=123456, status="replied")
    session.add(lead)
    session.commit()
    session.refresh(lead)

    session.add(
        LeadInteraction(
            lead_id=lead.id,
            direction="inbound",
            content="first",
        )
    )
    session.add(
        LeadInteraction(
            lead_id=lead.id,
            direction="outbound",
            content="second",
        )
    )
    session.commit()

    response = client.get(f"/api/v1/crm/leads/{lead.id}")

    assert response.status_code == 200
    assert [item["content"] for item in response.json()["interactions"]] == [
        "first",
        "second",
    ]
