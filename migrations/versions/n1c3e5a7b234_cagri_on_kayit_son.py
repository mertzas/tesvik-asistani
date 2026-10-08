"""tesvik_cagrilari.on_kayit_son: ön kayıt / kuruluş başvurusu son günü

TÜBİTAK TEYDEB çağrılarında firmanın son günü çağrı kapanışından önce (1501 2026-2: ön kayıt 22.10, kapanış 26.10).
Çip, "sıradaki adım" ve kalan gün bu tarihe göre hesaplanır (app/cagrilar.son_gun).

Revision ID: n1c3e5a7b234
Revises: m0b2d4f6a012
Create Date: 2026-10-09 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'n1c3e5a7b234'
down_revision: Union[str, None] = 'm0b2d4f6a012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tesvik_cagrilari') as batch_op:
        batch_op.add_column(sa.Column('on_kayit_son', sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('tesvik_cagrilari') as batch_op:
        batch_op.drop_column('on_kayit_son')
