"""Verify llm_usage has the 3 safety columns from migration c7d8e9f0a1b2."""
from sqlmodel import Session, select, text

from app.core.db import engine
from app.models.llm_usage import LLMUsage


def test_model_has_safety_fields():
    """Model defines the 3 safety fields."""
    fields = LLMUsage.model_fields
    assert "moderation_score" in fields
    assert "block_layer" in fields
    assert "routed_provider" in fields


def test_safety_columns_exist_in_db():
    """Migration applied — DB columns are queryable."""
    with Session(engine) as s:
        result = s.exec(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='llm_usage' "
            "AND column_name IN ('moderation_score','block_layer','routed_provider')"
        )).all()
        names = {row[0] for row in result}
        assert names == {"moderation_score", "block_layer", "routed_provider"}


def test_insert_row_with_safety_fields():
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
