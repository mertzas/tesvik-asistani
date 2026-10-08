"""tesvik_cagrilari: programların dönemsel başvuru çağrıları (açılış/kapanış, kaynak, doğrulama tarihi)

Revision ID: l9a1c3e5f901
Revises: k8f0b2c4d890
Create Date: 2026-10-08 23:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'l9a1c3e5f901'
down_revision: Union[str, None] = 'k8f0b2c4d890'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tesvik_cagrilari',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tesvik_id', sa.Integer(), sa.ForeignKey('tesvikler.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ad', sa.String(length=200), nullable=False),
        sa.Column('acilis', sa.Date(), nullable=True),
        sa.Column('kapanis', sa.Date(), nullable=True),
        sa.Column('kaynak_url', sa.String(), nullable=False),
        sa.Column('dogrulama_tarihi', sa.Date(), nullable=False),
        sa.Column('notlar', sa.Text(), nullable=True),
        sa.UniqueConstraint('tesvik_id', 'ad', name='uq_tesvik_cagri_ad'),
    )
    op.create_index('ix_tesvik_cagrilari_tesvik_id', 'tesvik_cagrilari', ['tesvik_id'])
    op.create_index('ix_tesvik_cagrilari_kapanis', 'tesvik_cagrilari', ['kapanis'])


def downgrade() -> None:
    op.drop_index('ix_tesvik_cagrilari_kapanis', table_name='tesvik_cagrilari')
    op.drop_index('ix_tesvik_cagrilari_tesvik_id', table_name='tesvik_cagrilari')
    op.drop_table('tesvik_cagrilari')
