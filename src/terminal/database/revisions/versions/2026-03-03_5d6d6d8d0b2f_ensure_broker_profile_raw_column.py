"""ensure_broker_profile_raw_column

Revision ID: 5d6d6d8d0b2f
Revises: d8c6a4f91be3
Create Date: 2026-03-03 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "5d6d6d8d0b2f"
down_revision: Union[str, Sequence[str], None] = "d8c6a4f91be3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("broker_credentials")}
    if "profile_raw" not in cols:
        op.add_column(
            "broker_credentials",
            sa.Column("profile_raw", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("broker_credentials")}
    if "profile_raw" in cols:
        op.drop_column("broker_credentials", "profile_raw")
