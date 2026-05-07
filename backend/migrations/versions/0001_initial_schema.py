"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "supervisor", name="userrole", native_enum=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── product_and_services ───────────────────────────────────────────────
    op.create_table(
        "product_and_services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("qbo_id", sa.String(32), nullable=False),
        sa.Column("sync_token", sa.String(16), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("sku", sa.String(200), nullable=True),
        sa.Column("item_type", sa.String(64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fully_qualified_name", sa.String(500), nullable=True),
        sa.Column("taxable", sa.Boolean(), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("purchase_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("purchase_desc", sa.Text(), nullable=True),
        sa.Column("track_qty_on_hand", sa.Boolean(), nullable=True),
        sa.Column("qty_on_hand", sa.Numeric(18, 4), nullable=True),
        sa.Column("inv_start_date", sa.String(32), nullable=True),
        sa.Column("parent_qbo_id", sa.String(32), nullable=True),
        sa.Column("parent_name", sa.String(500), nullable=True),
        sa.Column("income_account_qbo_id", sa.String(32), nullable=True),
        sa.Column("expense_account_qbo_id", sa.String(32), nullable=True),
        sa.Column("asset_account_qbo_id", sa.String(32), nullable=True),
        sa.Column("qbo_last_updated", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qbo_id"),
    )
    op.create_index("ix_product_and_services_qbo_id", "product_and_services", ["qbo_id"])
    op.create_index("ix_product_and_services_name", "product_and_services", ["name"])
    op.create_index("ix_product_and_services_sku", "product_and_services", ["sku"])

    # ── customers ──────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="customerstatus", native_enum=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("qbo_id", sa.String(32), nullable=True),
        sa.Column("qbo_sync_token", sa.String(16), nullable=True),
        sa.Column("title", sa.String(40), nullable=True),
        sa.Column("given_name", sa.String(100), nullable=True),
        sa.Column("middle_name", sa.String(100), nullable=True),
        sa.Column("family_name", sa.String(100), nullable=True),
        sa.Column("suffix", sa.String(16), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("primary_email", sa.String(320), nullable=True),
        sa.Column("phone_number", sa.String(40), nullable=True),
        sa.Column("cc_email", sa.String(500), nullable=True),
        sa.Column("bcc_email", sa.String(500), nullable=True),
        sa.Column("mobile", sa.String(40), nullable=True),
        sa.Column("fax", sa.String(40), nullable=True),
        sa.Column("other_contact", sa.String(500), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("print_on_check_name", sa.String(500), nullable=True),
        sa.Column("billing_line1", sa.String(500), nullable=True),
        sa.Column("billing_line2", sa.String(500), nullable=True),
        sa.Column("billing_line3", sa.String(500), nullable=True),
        sa.Column("billing_line4", sa.String(500), nullable=True),
        sa.Column("billing_city", sa.String(255), nullable=True),
        sa.Column("billing_state", sa.String(255), nullable=True),
        sa.Column("billing_zip", sa.String(30), nullable=True),
        sa.Column("billing_country", sa.String(255), nullable=True),
        sa.Column("ship_same_as_billing", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("shipping_line1", sa.String(500), nullable=True),
        sa.Column("shipping_line2", sa.String(500), nullable=True),
        sa.Column("shipping_line3", sa.String(500), nullable=True),
        sa.Column("shipping_line4", sa.String(500), nullable=True),
        sa.Column("shipping_city", sa.String(255), nullable=True),
        sa.Column("shipping_state", sa.String(255), nullable=True),
        sa.Column("shipping_zip", sa.String(30), nullable=True),
        sa.Column("shipping_country", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("add_attachment_in_mail", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_pushed_to_qbo_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("qbo_last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qbo_id"),
    )
    op.create_index("ix_customers_status", "customers", ["status"])
    op.create_index("ix_customers_display_name", "customers", ["display_name"])
    op.create_index("ix_customers_qbo_id", "customers", ["qbo_id"])

    # ── customer_product_and_services (join table) ─────────────────────────
    op.create_table(
        "customer_product_and_services",
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("product_and_service_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["product_and_service_id"], ["product_and_services.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("customer_id", "product_and_service_id"),
    )

    # ── customer_attachments ───────────────────────────────────────────────
    op.create_table(
        "customer_attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_relpath", sa.String(1024), nullable=False),
        sa.Column("qbo_attachable_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_relpath"),
    )
    op.create_index("ix_customer_attachments_customer_id", "customer_attachments", ["customer_id"])

    # ── centers ────────────────────────────────────────────────────────────
    op.create_table(
        "centers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
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
        sa.ForeignKeyConstraint(["company_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_centers_company_name"),
    )
    op.create_index("ix_centers_company_id", "centers", ["company_id"])

    # ── invoices ───────────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
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
        sa.ForeignKeyConstraint(["company_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_company_id", "invoices", ["company_id"])

    # ── invoice_centers (join table) ───────────────────────────────────────
    op.create_table(
        "invoice_centers",
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("invoice_id", "center_id"),
    )

    # ── invoice_email_activity ─────────────────────────────────────────────
    op.create_table(
        "invoice_email_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("qbo_invoice_id", sa.String(32), nullable=False),
        sa.Column("doc_number", sa.String(64), nullable=False),
        sa.Column("customer_qbo_id", sa.String(32), nullable=True),
        sa.Column("customer_display_name", sa.String(500), nullable=False),
        sa.Column("email_status", sa.String(64), nullable=False),
        sa.Column("txn_date", sa.String(32), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invoice_email_activity_qbo_invoice_id", "invoice_email_activity", ["qbo_invoice_id"]
    )
    op.create_index(
        "ix_invoice_email_activity_customer_qbo_id",
        "invoice_email_activity",
        ["customer_qbo_id"],
    )


def downgrade() -> None:
    op.drop_table("invoice_email_activity")
    op.drop_table("invoice_centers")
    op.drop_table("invoices")
    op.drop_table("centers")
    op.drop_table("customer_attachments")
    op.drop_table("customer_product_and_services")
    op.drop_table("customers")
    op.drop_table("product_and_services")
    op.drop_table("users")
