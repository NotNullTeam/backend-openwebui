"""Merge multiple heads

Revision ID: ceeed12ad009
Revises: add_usage_logs, b1c2d3e4f5a6
Create Date: 2025-08-22 15:58:44.276134

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'ceeed12ad009'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
