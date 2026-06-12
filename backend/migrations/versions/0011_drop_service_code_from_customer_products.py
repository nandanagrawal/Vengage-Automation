"""Drop service_code_id from customer_product_and_services.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-11
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_cps_service_code_id", table_name="customer_product_and_services")
    op.drop_constraint("customer_product_and_services_service_code_id_fkey", "customer_product_and_services", type_="foreignkey")
    op.drop_column("customer_product_and_services", "service_code_id")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("customer_product_and_services", sa.Column("service_code_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "customer_product_and_services_service_code_id_fkey",
        "customer_product_and_services", "service_codes",
        ["service_code_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_customer_product_and_services_service_code_id", "customer_product_and_services", ["service_code_id"])
