"""Drop the old top-level product_column_mappings table.

Column mapping now lives per customer-service row (see 0016). Run
scripts/backfill_customer_service_columns.py BEFORE applying this migration
— it copies every existing product_column_mappings row down to the matching
customer_product_and_services rows. Once that's done and confirmed, this
table is safe to drop. Dropping the table also drops its indexes/constraints/
FKs (Postgres cascades that automatically) — downgrade() recreates the exact
shape the table had as of migration 0014 (its last change before this drop).

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("product_column_mappings")


def downgrade() -> None:
    op.create_table(
        "product_column_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_and_service_id", sa.Integer(), nullable=False),
        sa.Column("sheet_column_id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_and_service_id"], ["product_and_services.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sheet_column_id"], ["sheet_columns.id"], ondelete="RESTRICT",
            name="fk_product_column_mappings_sheet_column_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_and_service_id", name="uq_product_column_mapping_product"),
        sa.UniqueConstraint("sheet_column_id", name="uq_product_column_mappings_sheet_column_id"),
    )
    op.create_index(
        "ix_product_column_mappings_product_and_service_id",
        "product_column_mappings",
        ["product_and_service_id"],
    )
    op.create_index(
        "ix_product_column_mappings_sheet_column_id",
        "product_column_mappings",
        ["sheet_column_id"],
    )
