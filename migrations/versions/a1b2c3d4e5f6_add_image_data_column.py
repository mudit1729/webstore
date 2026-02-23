"""add image_data column for DB-based image storage

Revision ID: a1b2c3d4e5f6
Revises: 43e40ffecfcb
Create Date: 2026-02-22 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '43e40ffecfcb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('images', sa.Column('image_data', sa.LargeBinary(), nullable=True))


def downgrade():
    op.drop_column('images', 'image_data')
