"""Per-customer payment terms (invoice due date = TxnDate + payment_terms_days).

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="15"),
    )


def downgrade() -> None:
    op.drop_column("customers", "payment_terms_days")
