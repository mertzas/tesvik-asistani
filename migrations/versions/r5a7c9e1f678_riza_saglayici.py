"""organizations.ai_riza_saglayici: açık rıza hangi yapay zekâ sağlayıcısına verildi

2026-10-11: Anthropic API'si üründen çıkarıldı; yanıtlar varsayılan olarak yerel danışmandan gelir, isteğe bağlı dış
servis Gemini ya da OpenAI uyumlu bir uçtur (app/llm_saglayici.py). KVKK açık rızası belirli bir alıcıya verilir:
Anthropic'e verilmiş rıza Google'a aktarılmaz. Mevcut rızalar silinmez, verildikleri sağlayıcıyla işaretlenir
("anthropic:Anthropic PBC"); yeni sağlayıcı için geçersiz sayılır ve kullanıcıdan yeniden istenir.

Revision ID: r5a7c9e1f678
Revises: q4f6b8d0e567
Create Date: 2026-10-11 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'r5a7c9e1f678'
down_revision: Union[str, None] = 'q4f6b8d0e567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ESKI_SAGLAYICI = "anthropic:Anthropic PBC"


def upgrade() -> None:
    with op.batch_alter_table('organizations') as batch_op:
        batch_op.add_column(sa.Column('ai_riza_saglayici', sa.String(length=200), nullable=True))
    op.execute(sa.text("UPDATE organizations SET ai_riza_saglayici = :s WHERE ai_yurtdisi_riza")
               .bindparams(s=ESKI_SAGLAYICI))


def downgrade() -> None:
    with op.batch_alter_table('organizations') as batch_op:
        batch_op.drop_column('ai_riza_saglayici')
