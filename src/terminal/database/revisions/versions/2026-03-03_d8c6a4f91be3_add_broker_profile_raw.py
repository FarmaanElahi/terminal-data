"""add_broker_profile_raw

Revision ID: d8c6a4f91be3
Revises: b42f0d55f8da
Create Date: 2026-03-03 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "d8c6a4f91be3"
down_revision: Union[str, Sequence[str], None] = "b42f0d55f8da"
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
