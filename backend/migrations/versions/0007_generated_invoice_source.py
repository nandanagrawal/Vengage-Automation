"""make invoice_upload_id nullable and add source column to generated_invoices

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the NOT NULL constraint on invoice_upload_id so webhook-received invoices
    # can be stored without an upload record.
    with op.batch_alter_table("generated_invoices") as batch_op:
        batch_op.alter_column("invoice_upload_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("source", sa.String(32), nullable=False, server_default="platform"))


def downgrade() -> None:
    with op.batch_alter_table("generated_invoices") as batch_op:
        batch_op.drop_column("source")
        batch_op.alter_column("invoice_upload_id", existing_type=sa.Integer(), nullable=False)
