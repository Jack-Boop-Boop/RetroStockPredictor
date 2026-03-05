"""Add guest users + custom_agents table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Guest login: add is_guest column, make password_hash nullable ---
    op.add_column("users", sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.alter_column("users", "password_hash", nullable=True)

    # --- custom_agents table ---
    op.create_table(
        "custom_agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("custom_agents.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("custom_agents")
    op.drop_column("users", "is_guest")
    op.alter_column("users", "password_hash", nullable=False)
