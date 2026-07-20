"""add immutable history metadata to production_phase_versions

Revision ID: b7c8d9e0f1a2
Revises: a4c5d6e7f8b9
"""

from alembic import op
import sqlalchemy as sa


revision = "b7c8d9e0f1a2"
down_revision = "a4c5d6e7f8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("production_phase_versions") as batch:
        batch.add_column(
            sa.Column("label", sa.Text(), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("notes", sa.Text(), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "source",
                sa.String(length=32),
                nullable=False,
                server_default="manual",
            )
        )
        batch.add_column(
            sa.Column(
                "snapshot_schema_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch.create_check_constraint(
            "ck_production_phase_version_source",
            "source IN ('baseline', 'manual', 'generated', 'revision', 'imported')",
        )
        batch.create_check_constraint(
            "ck_production_phase_version_snapshot_schema",
            "snapshot_schema_version > 0",
        )

    # Honest backfill for rows that already exist (Phase 1 generate/revise history).
    op.execute(
        sa.text(
            """
            UPDATE production_phase_versions
            SET
                label = CASE
                    WHEN version_number = 1 THEN 'Generated package'
                    ELSE 'Revision ' || CAST(version_number AS TEXT)
                END,
                notes = '',
                source = CASE
                    WHEN version_number = 1 THEN 'generated'
                    ELSE 'revision'
                END,
                snapshot_schema_version = 1
            WHERE label = '' OR source = 'manual'
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("production_phase_versions") as batch:
        batch.drop_constraint(
            "ck_production_phase_version_snapshot_schema", type_="check"
        )
        batch.drop_constraint("ck_production_phase_version_source", type_="check")
        batch.drop_column("snapshot_schema_version")
        batch.drop_column("source")
        batch.drop_column("notes")
        batch.drop_column("label")
