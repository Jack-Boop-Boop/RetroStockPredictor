"""Initial schema: users, portfolios, positions, orders, fills, watchlists, candles, analysis.

Revision ID: 001
Revises: None
Create Date: 2025-03-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- portfolios ---
    op.create_table(
        "portfolios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False, server_default="Default"),
        sa.Column("initial_cash", sa.Numeric(15, 2), nullable=False, server_default=sa.text("100000")),
        sa.Column("cash", sa.Numeric(15, 2), nullable=False, server_default=sa.text("100000")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- positions ---
    op.create_table(
        "positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("symbol", sa.String(10), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(15, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_cost", sa.Numeric(15, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "symbol", name="uq_positions_portfolio_symbol"),
    )

    # --- orders ---
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("symbol", sa.String(10), nullable=False, index=True),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("order_type", sa.String(10), nullable=False, server_default="market"),
        sa.Column("quantity", sa.Numeric(15, 6), nullable=False),
        sa.Column("limit_price", sa.Numeric(15, 6), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("filled_quantity", sa.Numeric(15, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("filled_avg_price", sa.Numeric(15, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- fills ---
    op.create_table(
        "fills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(15, 6), nullable=False),
        sa.Column("price", sa.Numeric(15, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- watchlists ---
    op.create_table(
        "watchlists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False, server_default="Default"),
        sa.Column("symbols", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- candles ---
    op.create_table(
        "candles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(10), nullable=False, index=True),
        sa.Column("interval", sa.String(5), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("open", sa.Numeric(15, 6), nullable=False),
        sa.Column("high", sa.Numeric(15, 6), nullable=False),
        sa.Column("low", sa.Numeric(15, 6), nullable=False),
        sa.Column("close", sa.Numeric(15, 6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "interval", "timestamp", name="uq_candles_symbol_interval_ts"),
    )

    # --- analysis_runs ---
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("symbol", sa.String(10), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("final_signal", sa.String(10), nullable=True),
        sa.Column("final_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("final_reasoning", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- analysis_agent_outputs ---
    op.create_table(
        "analysis_agent_outputs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("signal", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("reasoning", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("analysis_agent_outputs")
    op.drop_table("analysis_runs")
    op.drop_table("candles")
    op.drop_table("watchlists")
    op.drop_table("fills")
    op.drop_table("orders")
    op.drop_table("positions")
    op.drop_table("portfolios")
    op.drop_table("users")
