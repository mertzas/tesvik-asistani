"""ikas_baglanti: İKAS App Store kurulumu (authorizedAppId, merchantId), son senkron özeti, webhook kaydı

Revision ID: k8f0b2c4d890
Revises: j7e9a1b3c789
Create Date: 2026-10-08 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'k8f0b2c4d890'
down_revision: Union[str, None] = 'j7e9a1b3c789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('ikas_baglanti', schema=None) as batch_op:
        batch_op.add_column(sa.Column('authorized_app_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('merchant_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('son_ozet', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('senkron_bekliyor', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('webhook_kaydi', sa.String(length=300), nullable=True))
        batch_op.create_index('ix_ikas_baglanti_authorized_app_id', ['authorized_app_id'], unique=False)
        batch_op.create_index('ix_ikas_baglanti_merchant_id', ['merchant_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('ikas_baglanti', schema=None) as batch_op:
        batch_op.drop_index('ix_ikas_baglanti_merchant_id')
        batch_op.drop_index('ix_ikas_baglanti_authorized_app_id')
        batch_op.drop_column('webhook_kaydi')
        batch_op.drop_column('senkron_bekliyor')
        batch_op.drop_column('son_ozet')
        batch_op.drop_column('merchant_id')
        batch_op.drop_column('authorized_app_id')
