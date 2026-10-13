"""financial_profiles: planlanan_yatirim_tl

9903 programlarının asgari sabit yatırım (MADDE 5/2) ve EK-3 tutar şartı profilde yatırım tutarı olmadığı için yalnız
soruda tutar verilince denetlenebiliyordu (docs/olcum/2026-10-09-100-ajan/RAPOR.md öneri 2). Alan isteğe bağlıdır;
boşsa eleme yapılmaz.

Revision ID: s6b8d0f2a789
Revises: r5a7c9e1f678
Create Date: 2026-10-13 04:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 's6b8d0f2a789'
down_revision: Union[str, None] = 'r5a7c9e1f678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('financial_profiles') as batch_op:
        batch_op.add_column(sa.Column('planlanan_yatirim_tl', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('financial_profiles') as batch_op:
        batch_op.drop_column('planlanan_yatirim_tl')
