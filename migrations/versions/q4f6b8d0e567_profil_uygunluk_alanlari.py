"""financial_profiles: kurucu_yasi, baska_sirkette_ortak, sertifikalar

Uygunluk ölçümü (docs/olcum/2026-10-09-uygunluk/RAPOR.md) kalan yanlış önerilerin profilde olmayan bilgiye bağlı
olduğunu gösterdi: 29 yaş sınırlı kredi 50 yaşındaki işletme sahibine, ortaklık yasaklı BiGG/1812 başka şirkette ortak
olan kişiye, organik tarım desteği sertifikasız çiftçiye öneriliyordu. Alanlar isteğe bağlıdır; boşsa eleme yapılmaz.

Revision ID: q4f6b8d0e567
Revises: p3e5a7c9d456
Create Date: 2026-10-10 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'q4f6b8d0e567'
down_revision: Union[str, None] = 'p3e5a7c9d456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('financial_profiles') as batch_op:
        batch_op.add_column(sa.Column('kurucu_yasi', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('baska_sirkette_ortak', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('sertifikalar', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('financial_profiles') as batch_op:
        batch_op.drop_column('sertifikalar')
        batch_op.drop_column('baska_sirkette_ortak')
        batch_op.drop_column('kurucu_yasi')
