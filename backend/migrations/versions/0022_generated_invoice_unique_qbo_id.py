"""Merge duplicate generated_invoices rows per QuickBooks invoice, then make
quickbooks_invoice_id unique.

Duplicates came from a race: QBO's "invoice created" webhook arrived while the
upload flow was still attaching Drive files, before it had saved its own row,
so the webhook inserted a second row (source='quickbooks', group = customer
name). Later "emailed" webhooks then updated only that copy, leaving the
upload's row stuck at pending.

Merge rule per quickbooks_invoice_id: keep the upload's row (it has the
centres and line items; lowest id if several), take send_status from the
most recently updated row of the group (that's the one webhooks were
updating) and the earliest non-null sent_at, then delete the other rows.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-13
"""
from __future__ import annotations

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT id, quickbooks_invoice_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY quickbooks_invoice_id
                       ORDER BY (invoice_upload_id IS NULL), id
                   ) AS keep_rank,
                   FIRST_VALUE(send_status) OVER (
                       PARTITION BY quickbooks_invoice_id ORDER BY updated_at DESC, id DESC
                   ) AS latest_status,
                   MIN(sent_at) OVER (PARTITION BY quickbooks_invoice_id) AS first_sent_at,
                   COUNT(*) OVER (PARTITION BY quickbooks_invoice_id) AS n
            FROM generated_invoices
            WHERE quickbooks_invoice_id IS NOT NULL
        )
        UPDATE generated_invoices g
        SET send_status = r.latest_status,
            sent_at = COALESCE(g.sent_at, r.first_sent_at)
        FROM ranked r
        WHERE g.id = r.id AND r.keep_rank = 1 AND r.n > 1
        """
    )
    op.execute(
        """
        DELETE FROM generated_invoices g
        USING (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY quickbooks_invoice_id
                ORDER BY (invoice_upload_id IS NULL), id
            ) AS keep_rank
            FROM generated_invoices
            WHERE quickbooks_invoice_id IS NOT NULL
        ) r
        WHERE g.id = r.id AND r.keep_rank > 1
        """
    )
    op.create_unique_constraint(
        "uq_generated_invoices_quickbooks_invoice_id", "generated_invoices", ["quickbooks_invoice_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_generated_invoices_quickbooks_invoice_id", "generated_invoices", type_="unique"
    )
