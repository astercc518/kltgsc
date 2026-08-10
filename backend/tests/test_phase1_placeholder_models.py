"""验证 Phase 1 占位模型 import 成功且对应 DB 表存在"""
import os
import pytest
from sqlmodel import Session, text


def test_models_importable():
    from app.models.case_study import CaseStudy
    from app.models.worker_persona import WorkerPersona
    from app.models.chitchat import ChitchatPool, ChitchatLog
    from app.models.ab_experiment import ABExperiment
    assert CaseStudy.__tablename__ == "case_studies"
    assert WorkerPersona.__tablename__ == "worker_personas"
    assert ChitchatPool.__tablename__ == "chitchat_pool"
    assert ChitchatLog.__tablename__ == "chitchat_log"
    assert ABExperiment.__tablename__ == "ab_experiments"


def test_tables_exist_in_db(session):
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("requires Postgres")
    rows = session.exec(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name IN ('case_studies','worker_personas','chitchat_pool',"
        "'chitchat_log','ab_experiments')"
    )).all()
    names = {r[0] for r in rows}
    assert names == {
        "case_studies", "worker_personas", "chitchat_pool",
        "chitchat_log", "ab_experiments"
    }
