"""make service_code_id nullable on customer_product_and_services

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("customer_product_and_services") as batch_op:
        batch_op.alter_column("service_code_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("customer_product_and_services") as batch_op:
        batch_op.alter_column("service_code_id", existing_type=sa.Integer(), nullable=False)
