"""tesvikler: kalici NACE kapsam karari (YATAY idempotency)

Revision ID: e1f4a6b8c234
Revises: d9e3f5a7b123
Create Date: 2026-10-06 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f4a6b8c234'
down_revision: Union[str, None] = 'd9e3f5a7b123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tesvikler', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nace_kapsam_turu', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('nace_kapsam_guven', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('nace_kapsam_kaynak', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('nace_kapsam_tarihi', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('tesvikler', schema=None) as batch_op:
        batch_op.drop_column('nace_kapsam_tarihi')
        batch_op.drop_column('nace_kapsam_kaynak')
        batch_op.drop_column('nace_kapsam_guven')
        batch_op.drop_column('nace_kapsam_turu')
