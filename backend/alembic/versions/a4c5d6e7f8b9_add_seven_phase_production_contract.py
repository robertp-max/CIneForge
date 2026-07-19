"""add the exact seven-phase production contract

Revision ID: a4c5d6e7f8b9
Revises: f3b4c5d6e7a8
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a4c5d6e7f8b9"
down_revision = "f3b4c5d6e7a8"
branch_labels = None
depends_on = None


def _uuid():
    return postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "production_phases",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("story_id", _uuid(), nullable=False),
        sa.Column("phase_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("current_version_number", sa.Integer(), nullable=True),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("locked_reason", sa.Text(), nullable=True),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        sa.Column("stale_reason", sa.Text(), nullable=True),
        sa.Column("generation_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "phase_number >= 1 AND phase_number <= 7",
            name="ck_production_phase_number",
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ("
            "'not_started', 'drafting', 'qa_pending', 'needs_revision', "
            "'ready_for_review', 'approved', 'blocked')",
            name="ck_production_phase_lifecycle_state",
        ),
        sa.CheckConstraint(
            "current_version_number IS NULL OR current_version_number > 0",
            name="ck_production_phase_current_version",
        ),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "phase_number", name="uq_production_phase_story_number"),
    )
    op.create_index("ix_production_phases_story_id", "production_phases", ["story_id"])
    op.create_index(
        "ix_production_phases_story_number",
        "production_phases",
        ["story_id", "phase_number"],
    )

    op.create_table(
        "production_phase_versions",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("production_phase_id", _uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("input_snapshot_json", _json(), nullable=False),
        sa.Column("output_json", _json(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("previous_version_id", _uuid(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version_number > 0", name="ck_production_phase_version_number"),
        sa.CheckConstraint(
            "lifecycle_state IN ("
            "'not_started', 'drafting', 'qa_pending', 'needs_revision', "
            "'ready_for_review', 'approved', 'blocked')",
            name="ck_production_phase_version_lifecycle_state",
        ),
        sa.ForeignKeyConstraint(
            ["production_phase_id"], ["production_phases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["previous_version_id"], ["production_phase_versions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "production_phase_id",
            "version_number",
            name="uq_production_phase_version",
        ),
    )
    op.create_index(
        "ix_production_phase_versions_production_phase_id",
        "production_phase_versions",
        ["production_phase_id"],
    )
    op.create_index(
        "ix_production_phase_versions_phase_version",
        "production_phase_versions",
        ["production_phase_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_production_phase_versions_phase_version",
        table_name="production_phase_versions",
    )
    op.drop_index(
        "ix_production_phase_versions_production_phase_id",
        table_name="production_phase_versions",
    )
    op.drop_table("production_phase_versions")
    op.drop_index("ix_production_phases_story_number", table_name="production_phases")
    op.drop_index("ix_production_phases_story_id", table_name="production_phases")
    op.drop_table("production_phases")
