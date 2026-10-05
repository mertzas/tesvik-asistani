"""profil nace_kodu ve tesvik_nace_association tablosu

Revision ID: c8d2e4f6a012
Revises: b7c1d3e5f901
Create Date: 2026-10-05 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8d2e4f6a012'
down_revision: Union[str, None] = 'b7c1d3e5f901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('financial_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nace_kodu', sa.String(length=10), nullable=True))
        batch_op.create_index('ix_financial_profiles_nace_kodu', ['nace_kodu'], unique=False)

    op.create_table(
        'tesvik_nace_association',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tesvik_id', sa.Integer(), nullable=False),
        sa.Column('nace_prefix', sa.String(length=10), nullable=False),
        sa.Column('kaynak', sa.String(length=60), nullable=False, server_default='elle'),
        sa.ForeignKeyConstraint(['tesvik_id'], ['tesvikler.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tesvik_id', 'nace_prefix', name='uq_tesvik_nace'),
    )
    op.create_index('ix_tesvik_nace_association_tesvik_id', 'tesvik_nace_association', ['tesvik_id'])
    op.create_index('ix_tesvik_nace_association_nace_prefix', 'tesvik_nace_association', ['nace_prefix'])


def downgrade() -> None:
    op.drop_index('ix_tesvik_nace_association_nace_prefix', table_name='tesvik_nace_association')
    op.drop_index('ix_tesvik_nace_association_tesvik_id', table_name='tesvik_nace_association')
    op.drop_table('tesvik_nace_association')

    with op.batch_alter_table('financial_profiles', schema=None) as batch_op:
        batch_op.drop_index('ix_financial_profiles_nace_kodu')
        batch_op.drop_column('nace_kodu')
