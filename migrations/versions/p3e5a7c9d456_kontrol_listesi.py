"""tesvikler.kontrol_listesi + tesvikler.basvuru_bicimi + basvuru_takipleri.uygunluk_cevaplari

Kontrol listesi denetimi (docs/olcum/2026-10-10-kontrol-listesi/RAPOR.md): maddelerin %27'si yanlış türdeydi (şart,
belge, adım, kural ve bilgi aynı onay kutusundaydı) ve kaynak alıntısı tutulmuyordu. kontrol_listesi her maddeyi türü,
resmî sayfadan alıntısı ve doğrulama durumuyla saklar; basvuru_bicimi (proje, kefalet, kredi, bildirim_prim ...) taslak
bölümünün gösterilip gösterilmeyeceğini belirler; uygunluk_cevaplari kullanıcının şartlara Evet/Hayır/Emin değilim
cevaplarıdır (belge/adım işaretlerinden ayrı).

Revision ID: p3e5a7c9d456
Revises: o2d4f6b8c345
Create Date: 2026-10-10 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'p3e5a7c9d456'
down_revision: Union[str, None] = 'o2d4f6b8c345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tesvikler') as batch_op:
        batch_op.add_column(sa.Column('kontrol_listesi', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('basvuru_bicimi', sa.String(length=20), nullable=True))
    with op.batch_alter_table('basvuru_takipleri') as batch_op:
        batch_op.add_column(sa.Column('uygunluk_cevaplari', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('basvuru_takipleri') as batch_op:
        batch_op.drop_column('uygunluk_cevaplari')
    with op.batch_alter_table('tesvikler') as batch_op:
        batch_op.drop_column('basvuru_bicimi')
        batch_op.drop_column('kontrol_listesi')
