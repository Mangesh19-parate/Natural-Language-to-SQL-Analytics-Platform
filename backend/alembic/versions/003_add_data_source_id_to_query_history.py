"""Add data_source_id to query_history table
 
Revision ID: 003_add_data_source_id_to_query_history
Revises: 002_add_evaluation_jobs
Create Date: 2026-09-20 14:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_add_data_source_id_to_query_history"
down_revision: Union[str, None] = "002_add_evaluation_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("query_history") as batch_op:
        batch_op.add_column(
            sa.Column(
                "data_source_id",
                sa.Integer(),
                sa.ForeignKey("data_sources.data_source_id", name="fk_query_history_data_source_id"),
                nullable=True,
            )
        )
        batch_op.create_index("ix_query_history_data_source_id", ["data_source_id"])


def downgrade() -> None:
    with op.batch_alter_table("query_history") as batch_op:
        batch_op.drop_index("ix_query_history_data_source_id")
        batch_op.drop_column("data_source_id")
