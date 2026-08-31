"""add_session_table

Revision ID: b8e88f36b3f6
Revises: 503a05e14a6e
Create Date: 2026-08-12 12:47:03.087834

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e88f36b3f6'
down_revision: Union[str, None] = '503a05e14a6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sessions table for database-backed revocable JWT sessions."""
    op.create_table(
        'sessions',
        sa.Column('session_id', sa.String(length=50), nullable=False),
        sa.Column('family_id', sa.String(length=50), nullable=False),
        sa.Column('rotation_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('purpose', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replaced_by', sa.String(length=50), nullable=True),
        sa.Column('revocation_reason', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('session_id'),
    )
    
    # Indexes for performance and integrity
    op.create_index('ix_sessions_token_hash', 'sessions', ['token_hash'], unique=True)
    op.create_index('ix_sessions_user_active', 'sessions', ['user_id', 'revoked_at', 'expires_at'])
    op.create_index('ix_sessions_cleanup', 'sessions', ['expires_at', 'revoked_at'])
    op.create_index('ix_sessions_family_rotation', 'sessions', ['family_id', 'rotation_id'], unique=True)
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])


def downgrade() -> None:
    """Remove sessions table."""
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_index('ix_sessions_family_rotation', table_name='sessions')
    op.drop_index('ix_sessions_cleanup', table_name='sessions')
    op.drop_index('ix_sessions_user_active', table_name='sessions')
    op.drop_index('ix_sessions_token_hash', table_name='sessions')
    op.drop_table('sessions')
