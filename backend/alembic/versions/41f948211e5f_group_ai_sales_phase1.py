"""group_ai_sales_phase1

Revision ID: 41f948211e5f
Revises: a4b5c6d7e8f9
Create Date: 2026-05-29

新增 6 张表 + 5 个字段，用于群内 AI 销售员 Phase 1-5 全功能落地。
Phase 1 实际只用 pending_replies + monitor.keyword_filters；
其余表/字段预先建好，后续 Phase 直接填充逻辑无需再迁移。

表名与现有迁移一致（单数）：customer, account, keywordmonitor, lead
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import pgvector.sqlalchemy

revision = "41f948211e5f"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === 现有表扩展 ===
    op.add_column("customer", sa.Column("icp_profile_text", sa.Text(), nullable=True))
    op.add_column("customer", sa.Column(
        "icp_profile_embedding",
        pgvector.sqlalchemy.Vector(768),
        nullable=True,
    ))
    op.add_column("customer", sa.Column(
        "lead_detector_thresholds", JSONB(),
        nullable=False,
        server_default='{"layer2_sim":0.55,"layer3_score":60,"layer3_confidence":0.7}',
    ))
    op.add_column("customer", sa.Column(
        "param_version", sa.Text(), nullable=False, server_default="v1"
    ))

    op.add_column("keywordmonitor", sa.Column("keyword_filters", JSONB(), nullable=True))

    # === pending_replies — 全管线状态机 ===
    op.create_table(
        "pending_replies",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("monitor_id", sa.Integer, sa.ForeignKey("keywordmonitor.id"), nullable=False),
        sa.Column("responder_account_id", sa.Integer, sa.ForeignKey("account.id"), nullable=True),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("message_id", sa.BigInteger, nullable=False),
        sa.Column("source_user_id", sa.BigInteger, nullable=False),
        sa.Column("source_text", sa.Text, nullable=False),
        sa.Column("layer1_matched", JSONB(), nullable=True),
        sa.Column("layer2_similarity", sa.Float, nullable=True),
        sa.Column("layer3_score", sa.Integer, nullable=True),
        sa.Column("layer3_needs", JSONB(), nullable=True),
        sa.Column("layer3_solution_topic", sa.Text, nullable=True),
        sa.Column("layer3_confidence", sa.Float, nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skip_reason", sa.Text, nullable=True),
        sa.Column("reply_text", sa.Text, nullable=True),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("lead.id"), nullable=True),
        sa.Column("experiment_tag", sa.Text, nullable=True),
    )
    op.create_index("idx_pending_replies_scan", "pending_replies", ["status", "fire_at"])
    op.create_index(
        "idx_pending_replies_dedup",
        "pending_replies",
        ["customer_id", "chat_id", "source_user_id", "created_at"],
    )

    # === case_studies — 成交案例库 ===
    op.create_table(
        "case_studies",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("industry", sa.Text, nullable=True),
        sa.Column("deal_size", sa.Text, nullable=True),
        sa.Column("period", sa.Text, nullable=True),
        sa.Column("problem", sa.Text, nullable=True),
        sa.Column("solution", sa.Text, nullable=True),
        sa.Column("outcome", sa.Text, nullable=True),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(768), nullable=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE INDEX idx_case_studies_emb ON case_studies "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_index(
        "idx_case_studies_customer", "case_studies", ["customer_id"],
        postgresql_where=sa.text("active = true"),
    )

    # === worker_personas — 账号人设 ===
    op.create_table(
        "worker_personas",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("account.id"), unique=True, nullable=False),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("display_name", sa.Text, nullable=True),
        sa.Column("age_range", sa.Text, nullable=True),
        sa.Column("region", sa.Text, nullable=True),
        sa.Column("occupation", sa.Text, nullable=True),
        sa.Column("speaking_style", sa.Text, nullable=True),
        sa.Column("catchphrases", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("active_hours", JSONB(), nullable=False, server_default=sa.text(
            "'{\"mon\":[[9,18]],\"tue\":[[9,18]],\"wed\":[[9,18]],\"thu\":[[9,18]],"
            "\"fri\":[[9,18]],\"sat\":[],\"sun\":[]}'::jsonb"
        )),
        sa.Column("daily_reply_quota", sa.Integer, nullable=False, server_default="5"),
        sa.Column("per_chat_daily_quota", sa.Integer, nullable=False, server_default="2"),
        sa.Column("per_chat_cooldown_minutes", sa.Integer, nullable=False, server_default="120"),
        sa.Column("daily_chitchat_quota", sa.Integer, nullable=False, server_default="7"),
        sa.Column("observation_window_seconds_range", JSONB(), nullable=False,
                  server_default=sa.text("'[60,900]'::jsonb")),
        sa.Column("typing_delay_seconds_range", JSONB(), nullable=False,
                  server_default=sa.text("'[30,120]'::jsonb")),
        sa.Column("param_version", sa.Text, nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === chitchat_pool — 闲聊话题库 ===
    op.create_table(
        "chitchat_pool",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=True),
        sa.Column("topic_category", sa.Text, nullable=True),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # === chitchat_log — 防重 + 审计 ===
    op.create_table(
        "chitchat_log",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("topic_id", sa.Integer, sa.ForeignKey("chitchat_pool.id"), nullable=True),
        sa.Column("sent_text", sa.Text, nullable=True),
        # NOTE: stored as TIMESTAMP (no TZ) so that ::date cast is IMMUTABLE,
        # enabling the expression index below. Application inserts UTC times.
        sa.Column("sent_at", sa.DateTime(timezone=False), server_default=sa.func.now()),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_chitchat_log_day ON chitchat_log "
        "(account_id, topic_id, chat_id, (sent_at::date))"
    )

    # === ab_experiments — A/B 实验框架（Phase 4 启用） ===
    op.create_table(
        "ab_experiments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("scope_value", sa.Integer, nullable=True),
        sa.Column("variants", JSONB(), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("primary_metric", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ab_experiments")
    op.execute("DROP INDEX IF EXISTS uq_chitchat_log_day")
    op.drop_table("chitchat_log")
    op.drop_table("chitchat_pool")
    op.drop_table("worker_personas")
    op.execute("DROP INDEX IF EXISTS idx_case_studies_customer")
    op.execute("DROP INDEX IF EXISTS idx_case_studies_emb")
    op.drop_table("case_studies")
    op.execute("DROP INDEX IF EXISTS idx_pending_replies_dedup")
    op.execute("DROP INDEX IF EXISTS idx_pending_replies_scan")
    op.drop_table("pending_replies")
    op.drop_column("keywordmonitor", "keyword_filters")
    op.drop_column("customer", "param_version")
    op.drop_column("customer", "lead_detector_thresholds")
    op.drop_column("customer", "icp_profile_embedding")
    op.drop_column("customer", "icp_profile_text")
