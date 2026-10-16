"""Add conversation_id to chat_history

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-10-15 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('chat_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('conversation_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_chat_history_conversation_id'), ['conversation_id'], unique=False)


def downgrade():
    with op.batch_alter_table('chat_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_history_conversation_id'))
        batch_op.drop_column('conversation_id')
