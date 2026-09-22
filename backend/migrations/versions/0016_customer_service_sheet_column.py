"""Move product-column mapping from the top-level ProductColumnMapping table
down to each CustomerProductAndService row, and add a per-row description.

sheet_column_id is nullable here — it's backfilled by
scripts/backfill_customer_service_columns.py from the (still-present at this
point) product_column_mappings table; see 0017 for dropping that table once
the backfill has run. The API requires sheet_column_id on every new/edited
row going forward (see CustomerServiceInput), but the DB column stays
nullable to allow that transitional window.

The old uq_customer_product constraint (customer_id, product_and_service_id)
is replaced with one that also includes sheet_column_id, so the same product
can be mapped twice for one customer as long as the column differs.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_product_and_services",
        sa.Column("sheet_column_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "customer_product_and_services",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_customer_product_and_services_sheet_column_id",
        "customer_product_and_services",
        "sheet_columns",
        ["sheet_column_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_customer_product_and_services_sheet_column_id",
        "customer_product_and_services",
        ["sheet_column_id"],
    )
    op.drop_constraint(
        "uq_customer_product", "customer_product_and_services", type_="unique"
    )
    op.create_unique_constraint(
        "uq_customer_product_column",
        "customer_product_and_services",
        ["customer_id", "product_and_service_id", "sheet_column_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_customer_product_column", "customer_product_and_services", type_="unique"
    )
    op.create_unique_constraint(
        "uq_customer_product",
        "customer_product_and_services",
        ["customer_id", "product_and_service_id"],
    )
    op.drop_index(
        "ix_customer_product_and_services_sheet_column_id",
        table_name="customer_product_and_services",
    )
    op.drop_constraint(
        "fk_customer_product_and_services_sheet_column_id",
        "customer_product_and_services",
        type_="foreignkey",
    )
    op.drop_column("customer_product_and_services", "description")
    op.drop_column("customer_product_and_services", "sheet_column_id")
