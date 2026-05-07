"""global center name uniqueness and invoice_uploads table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop per-customer unique constraint, replace with global unique on name
    op.drop_constraint("uq_centers_company_name", "centers", type_="unique")
    op.create_unique_constraint("uq_centers_name", "centers", ["name"])
    op.create_index("ix_centers_name", "centers", ["name"])

    # invoice_uploads — track every XLS/CSV upload and its generation result
    op.create_table(
        "invoice_uploads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("result_json", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("invoice_uploads")
    op.drop_index("ix_centers_name", "centers")
    op.drop_constraint("uq_centers_name", "centers", type_="unique")
    op.create_unique_constraint(
        "uq_centers_company_name", "centers", ["company_id", "name"]
    )
