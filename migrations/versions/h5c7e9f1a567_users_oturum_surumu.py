"""users.oturum_surumu: JWT iptali (parola sıfırlama / tüm oturumları kapat)

Belirteç "sv" talebinde bu sürümü taşır; sürüm artınca önceki belirteçler reddedilir. Mevcut satırlar 0 alır ve
"sv" talebi olmayan eski belirteçler de 0 sayıldığı için göç anında kimse oturumdan atılmaz.

Revision ID: h5c7e9f1a567
Revises: g4b6c8d0e456
Create Date: 2026-10-08 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'h5c7e9f1a567'
down_revision: Union[str, None] = 'g4b6c8d0e456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('oturum_surumu', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('oturum_surumu')
