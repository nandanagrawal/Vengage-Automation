"""generated invoices tables and upload count columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add tracking columns to invoice_uploads
    op.add_column("invoice_uploads", sa.Column("total_invoices", sa.Integer(), nullable=True))
    op.add_column("invoice_uploads", sa.Column("success_count", sa.Integer(), nullable=True))
    op.add_column("invoice_uploads", sa.Column("failed_count", sa.Integer(), nullable=True))
    op.add_column("invoice_uploads", sa.Column("errors_json", sa.Text(), nullable=True))

    # generated_invoices — one row per QBO invoice created by an upload
    op.create_table(
        "generated_invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_upload_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("quickbooks_invoice_id", sa.String(64), nullable=True),
        sa.Column("invoice_number", sa.String(64), nullable=True),
        sa.Column("center_group_name", sa.String(500), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("send_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["invoice_upload_id"], ["invoice_uploads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_invoices_upload_id", "generated_invoices", ["invoice_upload_id"])
    op.create_index("ix_generated_invoices_customer_id", "generated_invoices", ["customer_id"])

    # generated_invoice_centers — which centers contributed to each generated invoice
    op.create_table(
        "generated_invoice_centers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("generated_invoice_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=True),
        sa.Column("center_name", sa.String(500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["generated_invoice_id"], ["generated_invoices.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generated_invoice_centers_invoice_id",
        "generated_invoice_centers",
        ["generated_invoice_id"],
    )

    # generated_invoice_line_items — one row per product/service per generated invoice
    op.create_table(
        "generated_invoice_line_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("generated_invoice_id", sa.Integer(), nullable=False),
        sa.Column("product_and_service_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["generated_invoice_id"], ["generated_invoices.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_and_service_id"], ["product_and_services.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generated_invoice_line_items_invoice_id",
        "generated_invoice_line_items",
        ["generated_invoice_id"],
    )


def downgrade() -> None:
    op.drop_table("generated_invoice_line_items")
    op.drop_table("generated_invoice_centers")
    op.drop_table("generated_invoices")
    op.drop_column("invoice_uploads", "errors_json")
    op.drop_column("invoice_uploads", "failed_count")
    op.drop_column("invoice_uploads", "success_count")
    op.drop_column("invoice_uploads", "total_invoices")
