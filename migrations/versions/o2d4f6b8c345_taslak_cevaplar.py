"""basvuru_takipleri.taslak_cevaplar: taslak sihirbazı cevapları (JSON)

Yapay zekâsız şablon taslak, kullanıcının proje/gerekçe/faaliyet/bütçe cevaplarıyla cümle ve tablo kurar; cevaplar
taslak yeniden oluşturulduğunda kaybolmasın diye saklanır (app/sablon_taslak.py, app/basvuru_listesi.py).

Revision ID: o2d4f6b8c345
Revises: n1c3e5a7b234
Create Date: 2026-10-09 04:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'o2d4f6b8c345'
down_revision: Union[str, None] = 'n1c3e5a7b234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('basvuru_takipleri') as batch_op:
        batch_op.add_column(sa.Column('taslak_cevaplar', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('basvuru_takipleri') as batch_op:
        batch_op.drop_column('taslak_cevaplar')
