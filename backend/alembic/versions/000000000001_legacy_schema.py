"""Create the pre-Alembic schema expected by revision 5339f2871fae.

Revision ID: 000000000001
Revises:
"""
import json
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "000000000001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_LEGACY_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "legacy_schema_manifest.json"


def _normalize_sql(value: object) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).split())


def _normalize_options(options: dict | None) -> dict:
    return {
        str(key): options[key]
        for key in sorted(options or {})
        if options[key] not in (None, [], {})
    }


def _legacy_catalog_manifest(inspector: sa.Inspector) -> dict:
    """Build a stable, complete structural signature for the public schema."""
    dialect = inspector.bind.dialect
    table_names = sorted(
        set(inspector.get_table_names()) - {"alembic_version"}
    )
    tables: dict[str, dict] = {}

    for table in table_names:
        columns = sorted(
            (
                {
                    "name": column["name"],
                    "type": column["type"].compile(dialect=dialect).lower(),
                    "nullable": bool(column["nullable"]),
                    "default": _normalize_sql(column.get("default")),
                    "identity": _normalize_options(column.get("identity")),
                    "computed": _normalize_options(column.get("computed")),
                }
                for column in inspector.get_columns(table)
            ),
            key=lambda column: column["name"],
        )
        primary_key = inspector.get_pk_constraint(table)
        foreign_keys = sorted(
            (
                {
                    "name": foreign_key.get("name"),
                    "columns": foreign_key.get("constrained_columns") or [],
                    "referred_schema": foreign_key.get("referred_schema"),
                    "referred_table": foreign_key.get("referred_table"),
                    "referred_columns": foreign_key.get("referred_columns") or [],
                    "options": _normalize_options(foreign_key.get("options")),
                }
                for foreign_key in inspector.get_foreign_keys(table)
            ),
            key=lambda foreign_key: (
                foreign_key["name"] or "",
                foreign_key["columns"],
            ),
        )
        unique_constraints = sorted(
            (
                {
                    "name": constraint.get("name"),
                    "columns": constraint.get("column_names") or [],
                }
                for constraint in inspector.get_unique_constraints(table)
            ),
            key=lambda constraint: (
                constraint["name"] or "",
                constraint["columns"],
            ),
        )
        check_constraints = sorted(
            (
                {
                    "name": constraint.get("name"),
                    "sqltext": _normalize_sql(constraint.get("sqltext")),
                }
                for constraint in inspector.get_check_constraints(table)
            ),
            key=lambda constraint: (
                constraint["name"] or "",
                constraint["sqltext"] or "",
            ),
        )
        indexes = sorted(
            (
                {
                    "name": index.get("name"),
                    "columns": index.get("column_names") or [],
                    "expressions": [
                        _normalize_sql(expression)
                        for expression in index.get("expressions") or []
                    ],
                    "unique": bool(index.get("unique")),
                    "include_columns": index.get("include_columns") or [],
                    "duplicates_constraint": index.get("duplicates_constraint"),
                }
                for index in inspector.get_indexes(table)
            ),
            key=lambda index: index["name"] or "",
        )
        tables[table] = {
            "columns": columns,
            "primary_key": {
                "name": primary_key.get("name"),
                "columns": primary_key.get("constrained_columns") or [],
            },
            "foreign_keys": foreign_keys,
            "unique_constraints": unique_constraints,
            "check_constraints": check_constraints,
            "indexes": indexes,
        }

    return {
        "tables": tables,
        "views": sorted(inspector.get_view_names()),
        "sequences": sorted(inspector.get_sequence_names()),
    }


def _adopt_complete_unversioned_legacy_schema() -> bool:
    """Return True only for the exact legacy shape consumed by the next revision."""
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names()) - {"alembic_version"}
    if not existing_tables:
        return False

    if inspector.bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Refusing to adopt partial or unknown unversioned schema; "
            "legacy adoption is supported only on PostgreSQL"
        )

    expected = json.loads(_LEGACY_MANIFEST_PATH.read_text())
    actual = _legacy_catalog_manifest(inspector)
    if actual != expected:
        expected_tables = set(expected["tables"])
        actual_tables = set(actual["tables"])
        changed_tables = sorted(
            table
            for table in expected_tables & actual_tables
            if expected["tables"][table] != actual["tables"][table]
        )
        raise RuntimeError(
            "Refusing to adopt partial or unknown unversioned schema; "
            f"missing_tables={sorted(expected_tables - actual_tables)}, "
            f"unexpected_tables={sorted(actual_tables - expected_tables)}, "
            f"changed_tables={changed_tables}, "
            f"views_match={actual['views'] == expected['views']}, "
            f"sequences_match={actual['sequences'] == expected['sequences']}"
        )
    return True


def upgrade() -> None:
    # Alembic creates alembic_version before invoking this revision. A complete
    # pre-Alembic installation can therefore be adopted transactionally by
    # validating its exact legacy signature and letting Alembic record this base.
    if _adopt_complete_unversioned_legacy_schema():
        return
# ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ai_config',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('api_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('base_url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_config_is_default'), 'ai_config', ['is_default'], unique=False)
    op.create_index(op.f('ix_ai_config_name'), 'ai_config', ['name'], unique=False)
    op.create_table('ai_knowledge_base',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('auto_update', sa.Boolean(), nullable=False),
    sa.Column('source_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_knowledge_base_name'), 'ai_knowledge_base', ['name'], unique=False)
    op.create_table('ai_persona',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('system_prompt', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('tone', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('forbidden_topics', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('required_keywords', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('usage_count', sa.Integer(), nullable=False),
    sa.Column('avg_reply_rate', sa.Float(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('invitelog',
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('target_user_id', sa.Integer(), nullable=False),
    sa.Column('target_telegram_id', sa.BigInteger(), nullable=True),
    sa.Column('target_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('target_channel', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('target_channel_id', sa.BigInteger(), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('account_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=False),
    sa.Column('flood_wait_seconds', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invitelog_account_id'), 'invitelog', ['account_id'], unique=False)
    op.create_index(op.f('ix_invitelog_created_at'), 'invitelog', ['created_at'], unique=False)
    op.create_index(op.f('ix_invitelog_error_code'), 'invitelog', ['error_code'], unique=False)
    op.create_index(op.f('ix_invitelog_status'), 'invitelog', ['status'], unique=False)
    op.create_index(op.f('ix_invitelog_target_telegram_id'), 'invitelog', ['target_telegram_id'], unique=False)
    op.create_index(op.f('ix_invitelog_target_user_id'), 'invitelog', ['target_user_id'], unique=False)
    op.create_index(op.f('ix_invitelog_task_id'), 'invitelog', ['task_id'], unique=False)
    op.create_table('invitetask',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('target_channel', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('source_group', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('account_ids_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('target_user_ids_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('account_group', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('total_count', sa.Integer(), nullable=False),
    sa.Column('success_count', sa.Integer(), nullable=False),
    sa.Column('fail_count', sa.Integer(), nullable=False),
    sa.Column('privacy_restricted_count', sa.Integer(), nullable=False),
    sa.Column('flood_wait_count', sa.Integer(), nullable=False),
    sa.Column('pending_count', sa.Integer(), nullable=False),
    sa.Column('min_delay', sa.Integer(), nullable=False),
    sa.Column('max_delay', sa.Integer(), nullable=False),
    sa.Column('max_invites_per_account', sa.Integer(), nullable=False),
    sa.Column('max_invites_per_task', sa.Integer(), nullable=False),
    sa.Column('concurrent_accounts', sa.Integer(), nullable=False),
    sa.Column('stop_on_flood', sa.Boolean(), nullable=False),
    sa.Column('filter_tags', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('filter_min_score', sa.Integer(), nullable=True),
    sa.Column('filter_funnel_stages', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('exclude_invited', sa.Boolean(), nullable=False),
    sa.Column('exclude_failed_recently', sa.Boolean(), nullable=False),
    sa.Column('failed_cooldown_hours', sa.Integer(), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(), nullable=True),
    sa.Column('is_recurring', sa.Boolean(), nullable=False),
    sa.Column('recurring_interval_hours', sa.Integer(), nullable=False),
    sa.Column('recurring_batch_size', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invitetask_account_group'), 'invitetask', ['account_group'], unique=False)
    op.create_index(op.f('ix_invitetask_status'), 'invitetask', ['status'], unique=False)
    op.create_table('operationlog',
    sa.Column('action', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('details', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('ip_address', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('proxy',
    sa.Column('ip', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('port', sa.Integer(), nullable=False),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('password', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('protocol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('provider_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('country', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('fail_count', sa.Integer(), nullable=False),
    sa.Column('last_checked', sa.DateTime(), nullable=True),
    sa.Column('expire_time', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proxy_ip'), 'proxy', ['ip'], unique=False)
    op.create_table('scrapingtask',
    sa.Column('task_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('account_ids_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_links_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('result_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('success_count', sa.Integer(), nullable=False),
    sa.Column('fail_count', sa.Integer(), nullable=False),
    sa.Column('error_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('celery_task_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('script',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('topic', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('roles_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('lines_json', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sendtask',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('message_content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('total_count', sa.Integer(), nullable=False),
    sa.Column('success_count', sa.Integer(), nullable=False),
    sa.Column('fail_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('min_delay', sa.Integer(), nullable=False),
    sa.Column('max_delay', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sourcegroup',
    sa.Column('link', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('risk_level', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('member_count', sa.Integer(), nullable=False),
    sa.Column('total_scraped', sa.Integer(), nullable=False),
    sa.Column('high_value_count', sa.Integer(), nullable=False),
    sa.Column('ai_score', sa.Integer(), nullable=True),
    sa.Column('ai_analysis', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('last_scraped_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sourcegroup_link'), 'sourcegroup', ['link'], unique=False)
    op.create_index(op.f('ix_sourcegroup_status'), 'sourcegroup', ['status'], unique=False)
    op.create_index(op.f('ix_sourcegroup_type'), 'sourcegroup', ['type'], unique=False)
    op.create_table('systemconfig',
    sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('value', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('targetuser',
    sa.Column('telegram_id', sa.BigInteger(), nullable=True),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('first_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('last_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('source_group', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('source_group_id', sa.BigInteger(), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('last_active', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('engagement_score', sa.Integer(), nullable=False),
    sa.Column('marketing_stage', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('tags', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('last_hit_keyword', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('last_hit_at', sa.DateTime(), nullable=True),
    sa.Column('ai_score', sa.Integer(), nullable=True),
    sa.Column('ai_tags', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('ai_summary', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('funnel_stage', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('invite_status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('invite_target_group', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('invite_account_id', sa.Integer(), nullable=True),
    sa.Column('invite_attempted_at', sa.DateTime(), nullable=True),
    sa.Column('invite_success_at', sa.DateTime(), nullable=True),
    sa.Column('invite_error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('invite_error_message', sa.Text(), nullable=True),
    sa.Column('invite_attempt_count', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_targetuser_invite_account_id'), 'targetuser', ['invite_account_id'], unique=False)
    op.create_index(op.f('ix_targetuser_invite_attempted_at'), 'targetuser', ['invite_attempted_at'], unique=False)
    op.create_index(op.f('ix_targetuser_invite_status'), 'targetuser', ['invite_status'], unique=False)
    op.create_index(op.f('ix_targetuser_telegram_id'), 'targetuser', ['telegram_id'], unique=True)
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('hashed_password', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('totp_secret', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('totp_enabled', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)
    op.create_table('warmuptask',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('action_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('account_ids_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('min_delay', sa.Integer(), nullable=False),
    sa.Column('max_delay', sa.Integer(), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('target_channels', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('success_count', sa.Integer(), nullable=False),
    sa.Column('fail_count', sa.Integer(), nullable=False),
    sa.Column('error_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('warmuptemplate',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('action_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('min_delay', sa.Integer(), nullable=False),
    sa.Column('max_delay', sa.Integer(), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('target_channels', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_warmuptemplate_name'), 'warmuptemplate', ['name'], unique=False)
    op.create_table('account',
    sa.Column('phone_number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('api_id', sa.Integer(), nullable=True),
    sa.Column('api_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('session_string', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('session_file_path', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('last_active', sa.DateTime(), nullable=True),
    sa.Column('proxy_id', sa.Integer(), nullable=True),
    sa.Column('device_model', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('system_version', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('app_version', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('cooldown_until', sa.DateTime(), nullable=True),
    sa.Column('auto_reply', sa.Boolean(), nullable=False),
    sa.Column('persona_prompt', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('tier', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('tags', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('combat_role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('health_score', sa.Integer(), nullable=False),
    sa.Column('daily_action_count', sa.Integer(), nullable=False),
    sa.Column('last_error_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['proxy_id'], ['proxy.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_account_phone_number'), 'account', ['phone_number'], unique=True)
    op.create_index(op.f('ix_account_role'), 'account', ['role'], unique=False)
    op.create_index(op.f('ix_account_tier'), 'account', ['tier'], unique=False)
    op.create_table('campaign',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('allowed_roles', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('daily_budget', sa.Integer(), nullable=False),
    sa.Column('daily_account_limit', sa.Integer(), nullable=False),
    sa.Column('ai_persona_id', sa.Integer(), nullable=True),
    sa.Column('total_messages_sent', sa.Integer(), nullable=False),
    sa.Column('total_replies_received', sa.Integer(), nullable=False),
    sa.Column('total_conversions', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['ai_persona_id'], ['ai_persona.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('scripttask',
    sa.Column('script_id', sa.Integer(), nullable=False),
    sa.Column('target_group', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('account_mapping_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('current_step', sa.Integer(), nullable=False),
    sa.Column('min_delay', sa.Integer(), nullable=False),
    sa.Column('max_delay', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['script_id'], ['script.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('accountsendstats',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('stat_date', sa.Date(), nullable=False),
    sa.Column('send_count', sa.Integer(), nullable=False),
    sa.Column('success_count', sa.Integer(), nullable=False),
    sa.Column('fail_count', sa.Integer(), nullable=False),
    sa.Column('last_send_at', sa.DateTime(), nullable=True),
    sa.Column('first_send_at', sa.DateTime(), nullable=True),
    sa.Column('consecutive_sends', sa.Integer(), nullable=False),
    sa.Column('last_rest_at', sa.DateTime(), nullable=True),
    sa.Column('flood_wait_count', sa.Integer(), nullable=False),
    sa.Column('error_count', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accountsendstats_account_id'), 'accountsendstats', ['account_id'], unique=False)
    op.create_index(op.f('ix_accountsendstats_stat_date'), 'accountsendstats', ['stat_date'], unique=False)
    op.create_table('campaign_knowledge_link',
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('knowledge_base_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
    sa.ForeignKeyConstraint(['knowledge_base_id'], ['ai_knowledge_base.id'], ),
    sa.PrimaryKeyConstraint('campaign_id', 'knowledge_base_id')
    )
    op.create_table('chathistory',
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('target_user_id', sa.Integer(), nullable=True),
    sa.Column('target_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chathistory_account_id'), 'chathistory', ['account_id'], unique=False)
    op.create_index(op.f('ix_chathistory_target_user_id'), 'chathistory', ['target_user_id'], unique=False)
    op.create_table('funnelgroup',
    sa.Column('link', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=True),
    sa.Column('welcome_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('auto_kick_ads', sa.Boolean(), nullable=False),
    sa.Column('member_count', sa.Integer(), nullable=False),
    sa.Column('today_joined', sa.Integer(), nullable=False),
    sa.Column('today_left', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_funnelgroup_campaign_id'), 'funnelgroup', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_funnelgroup_link'), 'funnelgroup', ['link'], unique=False)
    op.create_index(op.f('ix_funnelgroup_type'), 'funnelgroup', ['type'], unique=False)
    op.create_table('keywordmonitor',
    sa.Column('keyword', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('match_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('target_groups', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('action_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('reply_script_id', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('forward_target', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('ai_reply_prompt', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('cooldown_seconds', sa.Integer(), nullable=False),
    sa.Column('auto_capture_lead', sa.Boolean(), nullable=False),
    sa.Column('score_weight', sa.Integer(), nullable=False),
    sa.Column('scenario_description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('auto_keywords', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('similarity_threshold', sa.Integer(), nullable=False),
    sa.Column('marketing_mode', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('reply_mode', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('delay_min_seconds', sa.Integer(), nullable=False),
    sa.Column('delay_max_seconds', sa.Integer(), nullable=False),
    sa.Column('enable_account_rotation', sa.Boolean(), nullable=False),
    sa.Column('max_replies_per_day', sa.Integer(), nullable=False),
    sa.Column('daily_reply_count', sa.Integer(), nullable=False),
    sa.Column('last_reply_date', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('ai_persona', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=True),
    sa.Column('ai_persona_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['ai_persona_id'], ['ai_persona.id'], ),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_keywordmonitor_keyword'), 'keywordmonitor', ['keyword'], unique=False)
    op.create_table('lead',
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('telegram_user_id', sa.Integer(), nullable=False),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('first_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('last_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('tags_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('last_interaction_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lead_account_id'), 'lead', ['account_id'], unique=False)
    op.create_index(op.f('ix_lead_telegram_user_id'), 'lead', ['telegram_user_id'], unique=False)
    op.create_table('sendrecord',
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('target_user_id', sa.Integer(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('error_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], ),
    sa.ForeignKeyConstraint(['target_user_id'], ['targetuser.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['sendtask.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('keywordhit',
    sa.Column('keyword_monitor_id', sa.Integer(), nullable=True),
    sa.Column('source_group_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('source_group_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('source_user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('source_user_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('message_content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('message_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('detected_at', sa.DateTime(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['keyword_monitor_id'], ['keywordmonitor.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('leadinteraction',
    sa.Column('lead_id', sa.Integer(), nullable=False),
    sa.Column('direction', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('message_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
    # Orphaned legacy tables existed alongside SQLModel's sourcegroup and
    # funnelgroup tables. Revision 5339f2871fae removes these two copies.
    op.create_table(
        "source_group",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
    )
    op.create_table(
        "funnel_group",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False),
    )

    # Legacy installations created these indexes outside SQLModel metadata.
    # The next historical revision removes or replaces each one.
    op.create_index("idx_source_group_status", "source_group", ["status"])
    op.create_index("idx_source_group_type", "source_group", ["type"])
    op.create_index("idx_funnel_group_campaign", "funnel_group", ["campaign_id"])
    op.create_index("idx_funnel_group_type", "funnel_group", ["type"])
    op.create_index("idx_account_combat_role", "account", ["combat_role"])
    op.create_index("idx_account_health_score", "account", ["health_score"])
    op.create_index("idx_accountsendstats_account_id", "accountsendstats", ["account_id"])
    op.create_index("idx_accountsendstats_stat_date", "accountsendstats", ["stat_date"])
    op.create_index("idx_kb_name", "ai_knowledge_base", ["name"])
    op.create_index("idx_campaign_status", "campaign", ["status"])
    op.create_index("idx_targetuser_ai_score", "targetuser", ["ai_score"])
    op.create_index("idx_targetuser_funnel_stage", "targetuser", ["funnel_stage"])


def downgrade() -> None:
    op.drop_table("funnel_group")
    op.drop_table("source_group")
# ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('leadinteraction')
    op.drop_table('keywordhit')
    op.drop_table('sendrecord')
    op.drop_index(op.f('ix_lead_telegram_user_id'), table_name='lead')
    op.drop_index(op.f('ix_lead_account_id'), table_name='lead')
    op.drop_table('lead')
    op.drop_index(op.f('ix_keywordmonitor_keyword'), table_name='keywordmonitor')
    op.drop_table('keywordmonitor')
    op.drop_index(op.f('ix_funnelgroup_type'), table_name='funnelgroup')
    op.drop_index(op.f('ix_funnelgroup_link'), table_name='funnelgroup')
    op.drop_index(op.f('ix_funnelgroup_campaign_id'), table_name='funnelgroup')
    op.drop_table('funnelgroup')
    op.drop_index(op.f('ix_chathistory_target_user_id'), table_name='chathistory')
    op.drop_index(op.f('ix_chathistory_account_id'), table_name='chathistory')
    op.drop_table('chathistory')
    op.drop_table('campaign_knowledge_link')
    op.drop_index(op.f('ix_accountsendstats_stat_date'), table_name='accountsendstats')
    op.drop_index(op.f('ix_accountsendstats_account_id'), table_name='accountsendstats')
    op.drop_table('accountsendstats')
    op.drop_table('scripttask')
    op.drop_table('campaign')
    op.drop_index(op.f('ix_account_tier'), table_name='account')
    op.drop_index(op.f('ix_account_role'), table_name='account')
    op.drop_index(op.f('ix_account_phone_number'), table_name='account')
    op.drop_table('account')
    op.drop_index(op.f('ix_warmuptemplate_name'), table_name='warmuptemplate')
    op.drop_table('warmuptemplate')
    op.drop_table('warmuptask')
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_targetuser_telegram_id'), table_name='targetuser')
    op.drop_index(op.f('ix_targetuser_invite_status'), table_name='targetuser')
    op.drop_index(op.f('ix_targetuser_invite_attempted_at'), table_name='targetuser')
    op.drop_index(op.f('ix_targetuser_invite_account_id'), table_name='targetuser')
    op.drop_table('targetuser')
    op.drop_table('systemconfig')
    op.drop_index(op.f('ix_sourcegroup_type'), table_name='sourcegroup')
    op.drop_index(op.f('ix_sourcegroup_status'), table_name='sourcegroup')
    op.drop_index(op.f('ix_sourcegroup_link'), table_name='sourcegroup')
    op.drop_table('sourcegroup')
    op.drop_table('sendtask')
    op.drop_table('script')
    op.drop_table('scrapingtask')
    op.drop_index(op.f('ix_proxy_ip'), table_name='proxy')
    op.drop_table('proxy')
    op.drop_table('operationlog')
    op.drop_index(op.f('ix_invitetask_status'), table_name='invitetask')
    op.drop_index(op.f('ix_invitetask_account_group'), table_name='invitetask')
    op.drop_table('invitetask')
    op.drop_index(op.f('ix_invitelog_task_id'), table_name='invitelog')
    op.drop_index(op.f('ix_invitelog_target_user_id'), table_name='invitelog')
    op.drop_index(op.f('ix_invitelog_target_telegram_id'), table_name='invitelog')
    op.drop_index(op.f('ix_invitelog_status'), table_name='invitelog')
    op.drop_index(op.f('ix_invitelog_error_code'), table_name='invitelog')
    op.drop_index(op.f('ix_invitelog_created_at'), table_name='invitelog')
    op.drop_index(op.f('ix_invitelog_account_id'), table_name='invitelog')
    op.drop_table('invitelog')
    op.drop_table('ai_persona')
    op.drop_index(op.f('ix_ai_knowledge_base_name'), table_name='ai_knowledge_base')
    op.drop_table('ai_knowledge_base')
    op.drop_index(op.f('ix_ai_config_name'), table_name='ai_config')
    op.drop_index(op.f('ix_ai_config_is_default'), table_name='ai_config')
    op.drop_table('ai_config')
    # ### end Alembic commands ###
