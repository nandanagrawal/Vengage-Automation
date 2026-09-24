"""Fixed pricing type: a fixed quantity billed on every invoice run.

Adds customer_product_and_services.quantity (used only when
pricing_type = 'fixed'). pricing_type is a plain VARCHAR(16) with no CHECK
constraint (Enum(native_enum=False) without create_constraint), so the new
'fixed' value needs no schema change of its own. Fixed rows leave
sheet_column_id NULL — they don't read the sheet.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_product_and_services",
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customer_product_and_services", "quantity")
