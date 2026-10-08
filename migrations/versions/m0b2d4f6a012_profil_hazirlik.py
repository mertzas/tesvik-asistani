"""financial_profiles.hazirlik: hazırlık adımlarının durumu ve e-ihracat gider girdileri (JSON)

Profil kaydı `giderler` alanını her seferinde yeniden yazdığı için hazırlık bilgisi ayrı sütunda tutulur
(app/hazirlik.py, PUT /api/hazirlik).

Revision ID: m0b2d4f6a012
Revises: l9a1c3e5f901
Create Date: 2026-10-09 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'm0b2d4f6a012'
down_revision: Union[str, None] = 'l9a1c3e5f901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('financial_profiles') as batch_op:
        batch_op.add_column(sa.Column('hazirlik', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('financial_profiles') as batch_op:
        batch_op.drop_column('hazirlik')
