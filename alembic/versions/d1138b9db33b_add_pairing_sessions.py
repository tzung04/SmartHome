"""add_pairing_sessions

Revision ID: d1138b9db33b
Revises: d7f42d5657cd
Create Date: 2026-05-13 15:36:34.567060

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1138b9db33b'
down_revision: Union[str, None] = 'd7f42d5657cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pairing_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column(
            'mac_address',
            sa.String(length=17),
            nullable=False,
            comment='Board MAC — AA:BB:CC:DD:EE:FF'
        ),
        sa.Column(
            'board_type',
            sa.String(length=50),
            nullable=False,
            comment='Board type gửi kèm khi bấm nút'
        ),
        sa.Column(
            'firmware_version',
            sa.String(length=20),
            nullable=True,
            comment='Firmware version hiện tại của board'
        ),
        sa.Column(
            'expires_at',
            sa.DateTime(timezone=True),
            nullable=False,
            comment='Hết hạn sau 30s kể từ khi board bấm nút'
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
 
    op.create_index(
        op.f('ix_pairing_sessions_mac_address'),
        'pairing_sessions',
        ['mac_address'],
        unique=False   # board có thể tạo session mới sau khi session cũ hết hạn
    )
 
    op.create_index(
        op.f('ix_pairing_sessions_expires_at'),
        'pairing_sessions',
        ['expires_at'],
        unique=False    # cleanup service dùng để xóa expired sessions
    )
 
 
def downgrade() -> None:
    op.drop_index(op.f('ix_pairing_sessions_expires_at'), table_name='pairing_sessions')
    op.drop_index(op.f('ix_pairing_sessions_mac_address'), table_name='pairing_sessions')
    op.drop_table('pairing_sessions')