"""add_request_id_to_access_logs

Revision ID: d7f42d5657cd
Revises: ef74d4fc5931
Create Date: 2026-05-13 13:20:08.015218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7f42d5657cd'
down_revision: Union[str, None] = 'ef74d4fc5931'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'access_logs',
        sa.Column(
            'request_id',
            sa.String(36),  
            nullable=True
        )
    )
 
    op.create_index(
        op.f('ix_access_logs_request_id'),
        'access_logs',
        ['request_id'],
        unique=True   # mỗi request_id chỉ tương ứng 1 log
    )
 
 
def downgrade() -> None:
    op.drop_index(
        op.f('ix_access_logs_request_id'),
        table_name='access_logs'
    )
    op.drop_column('access_logs', 'request_id')
