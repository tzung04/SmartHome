"""add_pending_registrations

Revision ID: ef74d4fc5931
Revises: 9b3dddd653f1
Create Date: 2026-05-12 10:15:56.677377

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef74d4fc5931'
down_revision: Union[str, None] = '9b3dddd653f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pending_registrations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('otp_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_pending_registrations_email'),
        'pending_registrations', ['email'], unique=False
    )
    op.create_index(
        op.f('ix_pending_registrations_expires_at'),
        'pending_registrations', ['expires_at'], unique=False
    )
 
 
def downgrade() -> None:
    op.drop_index(
        op.f('ix_pending_registrations_expires_at'),
        table_name='pending_registrations'
    )
    op.drop_index(
        op.f('ix_pending_registrations_email'),
        table_name='pending_registrations'
    )
    op.drop_table('pending_registrations')