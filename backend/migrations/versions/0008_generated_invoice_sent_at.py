"""Add sent_at to generated_invoices

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("generated_invoices") as batch_op:
        batch_op.add_column(sa.Column("sent_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("generated_invoices") as batch_op:
        batch_op.drop_column("sent_at")
