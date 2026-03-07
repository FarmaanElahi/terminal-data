"""drop candle_data_refreshes table

Revision ID: 5636d474256a
Revises: fc690ed014eb
Create Date: 2026-03-08 00:23:53.783351

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5636d474256a'
down_revision: Union[str, Sequence[str], None] = 'fc690ed014eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('candle_data_refreshes')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        'candle_data_refreshes',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('exchange', sa.String(length=10), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('symbols_count', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index(op.f('ix_candle_data_refreshes_exchange'), 'candle_data_refreshes', ['exchange'], unique=False)
    op.create_index(op.f('ix_candle_data_refreshes_timeframe'), 'candle_data_refreshes', ['timeframe'], unique=False)
