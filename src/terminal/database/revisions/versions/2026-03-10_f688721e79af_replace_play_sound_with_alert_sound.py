"""replace_play_sound_with_alert_sound

Revision ID: f688721e79af
Revises: 1aab159d8a19
Create Date: 2026-03-10 13:53:27.005181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f688721e79af'
down_revision: Union[str, Sequence[str], None] = '1aab159d8a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('alerts', sa.Column('alert_sound', sa.String(), nullable=True))
    
    # Data migration
    # play_sound=True -> alert_sound='beep'
    # play_sound=False -> alert_sound='none'
    op.execute("UPDATE alerts SET alert_sound = 'beep' WHERE play_sound = TRUE")
    op.execute("UPDATE alerts SET alert_sound = 'none' WHERE play_sound = FALSE")
    
    # Set default for any nulls
    op.execute("UPDATE alerts SET alert_sound = 'beep' WHERE alert_sound IS NULL")
    
    op.drop_column('alerts', 'play_sound')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('alerts', sa.Column('play_sound', sa.BOOLEAN(), nullable=True))
    
    # Data migration back
    # alert_sound != 'none' -> play_sound=True
    # alert_sound == 'none' -> play_sound=False
    op.execute("UPDATE alerts SET play_sound = TRUE WHERE alert_sound != 'none'")
    op.execute("UPDATE alerts SET play_sound = FALSE WHERE alert_sound = 'none'")
    
    op.execute("UPDATE alerts SET play_sound = TRUE WHERE play_sound IS NULL")
    op.alter_column('alerts', 'play_sound', nullable=False)
    
    op.drop_column('alerts', 'alert_sound')
