"""tesvik_nace_association.haric_mi (acik dislama satirlari)

Revision ID: d9e3f5a7b123
Revises: c8d2e4f6a012
Create Date: 2026-10-06 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9e3f5a7b123'
down_revision: Union[str, None] = 'c8d2e4f6a012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tesvik_nace_association', schema=None) as batch_op:
        batch_op.add_column(sa.Column('haric_mi', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('tesvik_nace_association', schema=None) as batch_op:
        batch_op.drop_column('haric_mi')
