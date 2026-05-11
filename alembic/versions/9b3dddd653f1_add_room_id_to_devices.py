"""add room_id to devices

Revision ID: 9b3dddd653f1
Revises: 021c072ba7b5
Create Date: 2026-05-10 10:44:47.688449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b3dddd653f1'
down_revision: Union[str, None] = '021c072ba7b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Thêm room_id vào devices
    op.add_column('devices',
        sa.Column('room_id', sa.UUID(as_uuid=True), 
                  sa.ForeignKey('rooms.id', ondelete='SET NULL'),
                  nullable=True, index=True)
    )
    # Xóa room_id khỏi boards
    op.drop_constraint('boards_room_id_fkey', 'boards', type_='foreignkey')
    op.drop_index('ix_boards_room_id', table_name='boards')
    op.drop_column('boards', 'room_id')

def downgrade():
    op.drop_column('devices', 'room_id')
    op.add_column('boards',
        sa.Column('room_id', sa.UUID(as_uuid=True),
                  sa.ForeignKey('rooms.id', ondelete='SET NULL'),
                  nullable=True)
    )
