"""add local_runtime_assets catalog table

Revision ID: g4a5b6c7d8e9
Revises: b7c8d9e0f1a2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g4a5b6c7d8e9"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def _uuid():
    return postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")


def upgrade() -> None:
    op.create_table(
        "local_runtime_assets",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("model_category", sa.String(length=64), nullable=True),
        sa.Column("file_extension", sa.String(length=32), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("inferred_family", sa.String(length=64), nullable=True),
        sa.Column("inferred_base", sa.String(length=128), nullable=True),
        sa.Column("selector_value", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("is_present", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mtime_ns", sa.BigInteger(), nullable=True),
        sa.Column("linked_model_variant_id", _uuid(), nullable=True),
        sa.Column("linked_lora_id", _uuid(), nullable=True),
        sa.Column("linked_workflow_template_id", _uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["linked_model_variant_id"], ["model_variants.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["linked_lora_id"], ["loras.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["linked_workflow_template_id"],
            ["workflow_templates.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_path"),
    )
    op.create_index("ix_local_runtime_assets_asset_type", "local_runtime_assets", ["asset_type"])
    op.create_index("ix_local_runtime_assets_relative_path", "local_runtime_assets", ["relative_path"])
    op.create_index("ix_local_runtime_assets_sha256", "local_runtime_assets", ["sha256"])
    op.create_index("ix_local_runtime_assets_inferred_family", "local_runtime_assets", ["inferred_family"])
    op.create_index("ix_local_runtime_assets_is_present", "local_runtime_assets", ["is_present"])
    op.create_index(
        "ix_local_runtime_assets_type_present",
        "local_runtime_assets",
        ["asset_type", "is_present"],
    )
    op.create_index(
        "ix_local_runtime_assets_family_base",
        "local_runtime_assets",
        ["inferred_family", "inferred_base"],
    )


def downgrade() -> None:
    op.drop_index("ix_local_runtime_assets_family_base", table_name="local_runtime_assets")
    op.drop_index("ix_local_runtime_assets_type_present", table_name="local_runtime_assets")
    op.drop_index("ix_local_runtime_assets_is_present", table_name="local_runtime_assets")
    op.drop_index("ix_local_runtime_assets_inferred_family", table_name="local_runtime_assets")
    op.drop_index("ix_local_runtime_assets_sha256", table_name="local_runtime_assets")
    op.drop_index("ix_local_runtime_assets_relative_path", table_name="local_runtime_assets")
    op.drop_index("ix_local_runtime_assets_asset_type", table_name="local_runtime_assets")
    op.drop_table("local_runtime_assets")
