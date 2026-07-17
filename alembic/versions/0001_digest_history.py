"""Create durable data-center digest history tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_digest_history"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "digest_entries",
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_published_at", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("telegram_message_id", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("source_url"),
    )
    op.create_index("ix_digest_entries_status", "digest_entries", ["status"])
    op.create_table(
        "digest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("candidates", sa.Integer(), nullable=False),
        sa.Column("attempted", sa.Integer(), nullable=False),
        sa.Column("published", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("digest_runs")
    op.drop_index("ix_digest_entries_status", table_name="digest_entries")
    op.drop_table("digest_entries")
