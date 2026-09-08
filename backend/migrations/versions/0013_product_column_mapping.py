"""Admin-configured product -> spreadsheet-column mapping.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_column_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_and_service_id", sa.Integer(), nullable=False),
        sa.Column("column_header", sa.String(500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_and_service_id"], ["product_and_services.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_and_service_id", name="uq_product_column_mapping_product"),
    )
    op.create_index(
        "ix_product_column_mappings_product_and_service_id",
        "product_column_mappings",
        ["product_and_service_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_column_mappings_product_and_service_id",
        table_name="product_column_mappings",
    )
    op.drop_table("product_column_mappings")
