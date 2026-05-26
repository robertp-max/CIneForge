"""add comfy job worker ownership

Revision ID: c4f8d3f2e1a9
Revises: 5a7d666d11d1
Create Date: 2026-05-26 06:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c4f8d3f2e1a9"
down_revision = "5a7d666d11d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comfy_jobs", sa.Column("worker_id", sa.Text(), nullable=True))
    op.add_column("comfy_jobs", sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("comfy_jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "comfy_jobs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("comfy_jobs", sa.Column("last_state_change_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "comfy_jobs",
        sa.Column(
            "recovery_metadata",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("comfy_jobs", "recovery_metadata")
    op.drop_column("comfy_jobs", "last_state_change_at")
    op.drop_column("comfy_jobs", "attempt_count")
    op.drop_column("comfy_jobs", "heartbeat_at")
    op.drop_column("comfy_jobs", "reserved_at")
    op.drop_column("comfy_jobs", "worker_id")
