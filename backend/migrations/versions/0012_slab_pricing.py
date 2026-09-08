"""Explicit flat/slab pricing on customer_product_and_services.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pricing_type stored as a plain string (native_enum=False on the model side —
    # matches the existing customerstatus column, no DB-level ENUM type to manage).
    op.add_column(
        "customer_product_and_services",
        sa.Column(
            "pricing_type",
            sa.String(16),
            nullable=False,
            server_default="flat",
        ),
    )
    # Only meaningful for flat rows now; slab rows carry their rates on the child table.
    op.alter_column(
        "customer_product_and_services", "rate", existing_type=sa.Numeric(18, 4), nullable=True
    )

    op.create_table(
        "customer_product_and_service_slabs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_product_and_service_id", sa.Integer(), nullable=False),
        sa.Column("range_start", sa.Integer(), nullable=False),
        sa.Column("range_end", sa.Integer(), nullable=True),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_product_and_service_id"],
            ["customer_product_and_services.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_product_and_service_id", "range_start", name="uq_cps_slab_range_start"
        ),
    )
    op.create_index(
        "ix_cps_slabs_customer_product_and_service_id",
        "customer_product_and_service_slabs",
        ["customer_product_and_service_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cps_slabs_customer_product_and_service_id",
        table_name="customer_product_and_service_slabs",
    )
    op.drop_table("customer_product_and_service_slabs")

    op.alter_column(
        "customer_product_and_services", "rate", existing_type=sa.Numeric(18, 4), nullable=False
    )
    op.drop_column("customer_product_and_services", "pricing_type")
