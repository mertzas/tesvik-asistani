"""basvuru_takipleri.taslak*: yapay zekâ başvuru ön taslağı (app/basvuru_taslagi.py)

Revision ID: j7e9a1b3c789
Revises: i6d8f0a2b678
Create Date: 2026-10-08 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'j7e9a1b3c789'
down_revision: Union[str, None] = 'i6d8f0a2b678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('basvuru_takipleri', schema=None) as batch_op:
        batch_op.add_column(sa.Column('taslak', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('taslak_tarihi', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('taslak_model', sa.String(length=60), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('basvuru_takipleri', schema=None) as batch_op:
        batch_op.drop_column('taslak_model')
        batch_op.drop_column('taslak_tarihi')
        batch_op.drop_column('taslak')
