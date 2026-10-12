"""Per-customer display/invoice order for service rows.

- customer_product_and_services.position: 0-based order within one
  customer, set from the row order on the customer edit page (drag & drop).
  Invoice lines follow it. Backfilled from the existing id order so nothing
  moves until someone reorders.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_product_and_services",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        """
        UPDATE customer_product_and_services AS c
        SET position = r.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY id) - 1 AS rn
            FROM customer_product_and_services
        ) AS r
        WHERE c.id = r.id
        """
    )


def downgrade() -> None:
    op.drop_column("customer_product_and_services", "position")
