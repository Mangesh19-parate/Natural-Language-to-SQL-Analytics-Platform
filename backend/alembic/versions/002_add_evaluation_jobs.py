"""Add evaluation_jobs table

Revision ID: 002_add_evaluation_jobs
Revises: 001_initial_metadata_schema
Create Date: 2026-09-19 21:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_add_evaluation_jobs"
down_revision: Union[str, None] = "001_initial_metadata_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_jobs",
        sa.Column("job_id", sa.String(36), primary_key=True, index=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("progress_pct", sa.Numeric(5, 2), server_default="0.0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("evaluation_jobs")
