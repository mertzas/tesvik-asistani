"""financial_profiles: sirket_turu, kurulus_tarihi, trl (girisim modu / HUKS)

Revision ID: f3a5b7c9d345
Revises: e1f4a6b8c234
Create Date: 2026-10-07 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a5b7c9d345'
down_revision: Union[str, None] = 'e1f4a6b8c234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('financial_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sirket_turu', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('kurulus_tarihi', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('trl', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('financial_profiles', schema=None) as batch_op:
        batch_op.drop_column('trl')
        batch_op.drop_column('kurulus_tarihi')
        batch_op.drop_column('sirket_turu')
