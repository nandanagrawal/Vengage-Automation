"""Partner customers (centre-scoped services), explicit Drive filenames per
centre, and the "input" pricing type.

- centers.drive_file_names: comma-separated exact Drive file name(s) for that
  centre, replacing the old "derive from Center.name" fuzzy match.
- customers.category: 'direct' (default, today's behavior) or 'partner'
  (every service row is scoped to one centre instead of customer-wide).
- customer_product_and_services.center_id: nullable FK to centers — NULL for
  customer-wide rows, set for centre-scoped ones. uq_customer_product_column
  widens to include it so the same (product, column) pair can be reused
  across different centres.
- No schema change needed for the new 'input' pricing_type value itself —
  pricing_type is a plain VARCHAR(16) with no CHECK constraint (same as when
  'fixed' was added in 0018).

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "centers",
        sa.Column("drive_file_names", sa.Text(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column(
            "category", sa.String(length=16), nullable=False, server_default="direct"
        ),
    )
    op.add_column(
        "customer_product_and_services",
        sa.Column("center_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_customer_product_and_services_center_id",
        "customer_product_and_services",
        "centers",
        ["center_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_customer_product_and_services_center_id",
        "customer_product_and_services",
        ["center_id"],
    )
    op.drop_constraint(
        "uq_customer_product_column", "customer_product_and_services", type_="unique"
    )
    op.create_unique_constraint(
        "uq_customer_product_column",
        "customer_product_and_services",
        ["customer_id", "product_and_service_id", "sheet_column_id", "center_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_customer_product_column", "customer_product_and_services", type_="unique"
    )
    op.create_unique_constraint(
        "uq_customer_product_column",
        "customer_product_and_services",
        ["customer_id", "product_and_service_id", "sheet_column_id"],
    )
    op.drop_index(
        "ix_customer_product_and_services_center_id",
        table_name="customer_product_and_services",
    )
    op.drop_constraint(
        "fk_customer_product_and_services_center_id",
        "customer_product_and_services",
        type_="foreignkey",
    )
    op.drop_column("customer_product_and_services", "center_id")
    op.drop_column("customers", "category")
    op.drop_column("centers", "drive_file_names")
