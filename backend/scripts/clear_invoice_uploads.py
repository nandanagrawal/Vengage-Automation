#!/usr/bin/env python3
"""
Delete all uploaded invoice-generation Excel/CSV sheets and the invoices
generated from them, then reset the id sequences back to 1.

invoice_uploads cascades (ON DELETE CASCADE) to generated_invoices, which in
turn cascades to generated_invoice_centers and generated_invoice_line_items —
so truncating invoice_uploads clears all of it in one step.

Usage (from backend/):
  python -m scripts.clear_invoice_uploads             # delete everything
  python -m scripts.clear_invoice_uploads --dry-run   # preview counts only
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.generated_invoice import GeneratedInvoice
from app.models.invoice_upload import InvoiceUpload


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete all invoice uploads and generated invoices")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        upload_count = db.query(InvoiceUpload).count()
        invoice_count = db.query(GeneratedInvoice).count()

        if upload_count == 0 and invoice_count == 0:
            print("Nothing to delete — invoice_uploads and generated_invoices are already empty.")
            return

        print(f"Found {upload_count} uploaded sheet(s) and {invoice_count} generated invoice(s).")

        if args.dry_run:
            print("[DRY-RUN] Would TRUNCATE invoice_uploads (cascades to generated_invoices, "
                  "centers, line_items) and reset id sequences to 1.")
            return

        db.execute(text(
            "TRUNCATE TABLE invoice_uploads RESTART IDENTITY CASCADE"
        ))
        db.commit()
        print("Deleted all uploaded sheets and generated invoices. Id sequences reset to 1.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
