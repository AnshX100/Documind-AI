"""Expand documents.file_type to VARCHAR(255) for DOCX mime types

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-10-15 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a1b2'
down_revision = 'b2c3d4e5f6a1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.alter_column(
            'file_type',
            existing_type=sa.String(length=50),
            type_=sa.String(length=255),
            existing_nullable=False
        )


def downgrade():
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.alter_column(
            'file_type',
            existing_type=sa.String(length=255),
            type_=sa.String(length=50),
            existing_nullable=False
        )
