"""manual_baseline

Revision ID: 00b824ad6fdb
Revises: a793cd09e7a1
Create Date: 2026-02-12 22:49:06.709360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00b824ad6fdb'
down_revision: Union[str, Sequence[str], None] = 'a793cd09e7a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
