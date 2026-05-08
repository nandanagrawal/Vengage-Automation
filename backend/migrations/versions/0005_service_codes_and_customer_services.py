"""service_codes and customer_product_and_services restructure

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old simple join table
    op.drop_table("customer_product_and_services")

    # Remove rate column from customers
    op.drop_column("customers", "rate")

    # Create service_codes table
    op.create_table(
        "service_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(255), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_service_codes_code", "service_codes", ["code"])

    # Create new customer_product_and_services table (proper join model)
    op.create_table(
        "customer_product_and_services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("product_and_service_id", sa.Integer(), nullable=False),
        sa.Column("service_code_id", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_and_service_id"], ["product_and_services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_code_id"], ["service_codes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "product_and_service_id", name="uq_customer_product"),
    )
    op.create_index("ix_cps_customer_id", "customer_product_and_services", ["customer_id"])
    op.create_index("ix_cps_product_id", "customer_product_and_services", ["product_and_service_id"])
    op.create_index("ix_cps_service_code_id", "customer_product_and_services", ["service_code_id"])


def downgrade() -> None:
    op.drop_table("customer_product_and_services")
    op.drop_table("service_codes")

    op.add_column("customers", sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")))

    op.create_table(
        "customer_product_and_services",
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("product_and_service_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_and_service_id"], ["product_and_services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("customer_id", "product_and_service_id"),
    )
