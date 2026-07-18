"""add atomic project workspace creation replay records

Revision ID: f3b4c5d6e7a8
Revises: e1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f3b4c5d6e7a8"
down_revision = "e1a2b3c4d5e6"
branch_labels = None
depends_on = None


def _uuid():
    return postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")


def upgrade() -> None:
    op.create_table(
        "project_workspace_creations",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("project_id", _uuid(), nullable=False),
        sa.Column("story_id", _uuid(), nullable=False),
        sa.Column("settings_id", _uuid(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["settings_id"], ["project_storyboard_settings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("project_id"),
        sa.UniqueConstraint("story_id"),
        sa.UniqueConstraint("settings_id"),
    )


def downgrade() -> None:
    op.drop_table("project_workspace_creations")
