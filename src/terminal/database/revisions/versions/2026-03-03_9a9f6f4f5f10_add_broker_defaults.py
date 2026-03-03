"""add_broker_defaults

Revision ID: 9a9f6f4f5f10
Revises: 3863cf3354ad
Create Date: 2026-03-03 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9a9f6f4f5f10"
down_revision: Union[str, Sequence[str], None] = "3863cf3354ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "broker_defaults",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("capability", sa.String(), nullable=False),
        sa.Column("market", sa.String(), nullable=False),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "capability",
            "market",
            name="uq_broker_defaults_user_capability_market",
        ),
    )
    op.create_index(
        op.f("ix_broker_defaults_user_id"),
        "broker_defaults",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_broker_defaults_capability"),
        "broker_defaults",
        ["capability"],
        unique=False,
    )
    op.create_index(
        op.f("ix_broker_defaults_market"),
        "broker_defaults",
        ["market"],
        unique=False,
    )
    op.create_index(
        op.f("ix_broker_defaults_provider_id"),
        "broker_defaults",
        ["provider_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_broker_defaults_provider_id"), table_name="broker_defaults")
    op.drop_index(op.f("ix_broker_defaults_market"), table_name="broker_defaults")
    op.drop_index(op.f("ix_broker_defaults_capability"), table_name="broker_defaults")
    op.drop_index(op.f("ix_broker_defaults_user_id"), table_name="broker_defaults")
    op.drop_table("broker_defaults")
