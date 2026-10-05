"""profil hedef kitle ozellikleri (ozellikler)

Revision ID: b7c1d3e5f901
Revises: 92ad9aed8742
Create Date: 2026-10-05 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c1d3e5f901'
down_revision: Union[str, None] = '92ad9aed8742'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('financial_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ozellikler', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('financial_profiles', schema=None) as batch_op:
        batch_op.drop_column('ozellikler')
