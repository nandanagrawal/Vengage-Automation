"""Drop customer_attachments table

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-12
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("customer_attachments")


def downgrade():
    pass
