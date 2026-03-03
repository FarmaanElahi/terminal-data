"""add_broker_account_fields

Revision ID: b42f0d55f8da
Revises: 9a9f6f4f5f10
Create Date: 2026-03-03 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b42f0d55f8da"
down_revision: Union[str, Sequence[str], None] = "9a9f6f4f5f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "broker_credentials",
        sa.Column("account_id", sa.String(), nullable=True),
    )
    op.add_column(
        "broker_credentials",
        sa.Column("account_label", sa.String(), nullable=True),
    )
    op.add_column(
        "broker_credentials",
        sa.Column("account_owner", sa.String(), nullable=True),
    )
    op.create_index(
        op.f("ix_broker_credentials_account_id"),
        "broker_credentials",
        ["account_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_broker_credentials_account_id"),
        table_name="broker_credentials",
    )
    op.drop_column("broker_credentials", "account_owner")
    op.drop_column("broker_credentials", "account_label")
    op.drop_column("broker_credentials", "account_id")
