"""Verify llm_usage has the 3 safety columns from migration c7d8e9f0a1b2."""
from sqlalchemy import inspect
from sqlmodel import Session

from app.models.llm_usage import LLMUsage


def test_model_has_safety_fields():
    """Model defines the 3 safety fields."""
    fields = LLMUsage.model_fields
    assert "moderation_score" in fields
    assert "block_layer" in fields
    assert "routed_provider" in fields


def test_safety_columns_exist_in_db(engine):
    """The active database schema exposes all safety columns."""
    names = {column["name"] for column in inspect(engine).get_columns("llm_usage")}
    assert {"moderation_score", "block_layer", "routed_provider"} <= names


def test_insert_row_with_safety_fields(engine):
    """Round-trip a row with all 3 safety fields populated."""
    with Session(engine) as s:
        row = LLMUsage(
            provider="vertex", model="gemini-2.5-flash", source="t_safety_cols",
            input_tokens=0, output_tokens=0, cost_usd=0.0,
            moderation_score=0.42, block_layer="L1", routed_provider="deepseek",
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        try:
            assert row.id is not None
            assert row.moderation_score == 0.42
            assert row.block_layer == "L1"
            assert row.routed_provider == "deepseek"
        finally:
            s.delete(row)
            s.commit()
