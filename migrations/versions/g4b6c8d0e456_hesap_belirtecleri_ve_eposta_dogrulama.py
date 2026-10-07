"""hesap_belirtecleri tablosu (parola sıfırlama / e-posta doğrulama) + users.email_dogrulama_zamani

Revision ID: g4b6c8d0e456
Revises: f3a5b7c9d345
Create Date: 2026-10-07 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g4b6c8d0e456'
down_revision: Union[str, None] = 'f3a5b7c9d345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'hesap_belirtecleri',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('amac', sa.String(length=30), nullable=False),
        sa.Column('belirtec_ozeti', sa.String(length=64), nullable=False),
        sa.Column('olusturma', sa.DateTime(), nullable=False),
        sa.Column('bitis', sa.DateTime(), nullable=False),
        sa.Column('kullanildi', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_hesap_belirtecleri_user_id'), 'hesap_belirtecleri', ['user_id'], unique=False)
    op.create_index(op.f('ix_hesap_belirtecleri_belirtec_ozeti'), 'hesap_belirtecleri', ['belirtec_ozeti'], unique=True)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_dogrulama_zamani', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_dogrulama_zamani')
    op.drop_index(op.f('ix_hesap_belirtecleri_belirtec_ozeti'), table_name='hesap_belirtecleri')
    op.drop_index(op.f('ix_hesap_belirtecleri_user_id'), table_name='hesap_belirtecleri')
    op.drop_table('hesap_belirtecleri')
