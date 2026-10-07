"""basvuru_takipleri: başvuru kontrol listesi işaretleri (app/basvuru_listesi.py)

Revision ID: i6d8f0a2b678
Revises: h5c7e9f1a567
Create Date: 2026-10-08 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'i6d8f0a2b678'
down_revision: Union[str, None] = 'h5c7e9f1a567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'basvuru_takipleri',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('tesvik_id', sa.Integer(), nullable=False),
        sa.Column('isaretli', sa.JSON(), nullable=False),
        sa.Column('olusturma', sa.DateTime(), nullable=False),
        sa.Column('guncelleme', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['tesvik_id'], ['tesvikler.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'tesvik_id', name='uq_basvuru_takibi_org_tesvik'),
    )
    op.create_index(op.f('ix_basvuru_takipleri_org_id'), 'basvuru_takipleri', ['org_id'], unique=False)
    op.create_index(op.f('ix_basvuru_takipleri_tesvik_id'), 'basvuru_takipleri', ['tesvik_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_basvuru_takipleri_tesvik_id'), table_name='basvuru_takipleri')
    op.drop_index(op.f('ix_basvuru_takipleri_org_id'), table_name='basvuru_takipleri')
    op.drop_table('basvuru_takipleri')
