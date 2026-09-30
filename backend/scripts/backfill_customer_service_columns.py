#!/usr/bin/env python3
"""
One-off migration: copy the old top-level ProductColumnMapping (one column
per product, admin-configured on the /product-mapping page) down onto every
existing CustomerProductAndService row as its own sheet_column_id.

Background
----------
Column mapping used to live globally: one product -> one spreadsheet column,
shared by every customer. It now lives per customer-service row instead (see
migration 0016_customer_service_sheet_column), so the same product can read
its quantity from a different column depending on which customer it's billed
to, and can even be mapped twice for one customer against two columns.

This script is the one-time bridge: for every CustomerProductAndService row
that doesn't have a sheet_column_id yet, look up the OLD product_column_mappings
table by product_and_service_id and copy its sheet_column_id across. It reads
and writes customer_product_and_services with raw SQL throughout (never the
ORM model) because it's meant to run right after migration 0016, before the
schema has caught up to whatever the model looks like today — later columns
such as center_id (added in 0019) don't exist yet at that point, and an ORM
query always selects every column the current model declares, so it would
fail with "column ... does not exist" the moment the model gains a column
this script's target revision doesn't have. It's also meant to run BEFORE
migration 0017_drop_product_column_mapping removes product_column_mappings
for good.

A row whose product never had a top-level mapping is left unresolved
(sheet_column_id stays NULL) and listed at the end — exactly like today's
"no mapping configured" behavior, it just produces no invoice line item
until an admin sets a column for it by hand on the customer edit page.

Usage
-----
    cd backend

    # Dry run (default) — prints the full report, writes nothing.
    python scripts/backfill_customer_service_columns.py

    # Apply the reported changes.
    python scripts/backfill_customer_service_columns.py --apply
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.db.session import SessionLocal


@dataclass
class _Plan:
    cps_id: int
    customer_name: str
    product_name: str
    sheet_column_id: int | None   # None = no old mapping found for this product
    column_name: str | None


def _load_old_mappings(db) -> dict[int, tuple[int, str]]:
    """product_and_service_id -> (sheet_column_id, column_name), read via raw SQL
    since the ProductColumnMapping model no longer exists in the codebase."""
    rows = db.execute(
        text(
            "SELECT pcm.product_and_service_id, pcm.sheet_column_id, sc.name "
            "FROM product_column_mappings pcm "
            "JOIN sheet_columns sc ON sc.id = pcm.sheet_column_id"
        )
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def _discover(db) -> list[_Plan]:
    old_mappings = _load_old_mappings(db)

    rows = db.execute(
        text(
            "SELECT cps.id, cps.product_and_service_id, "
            "       COALESCE(cust.display_name, 'customer#' || cps.customer_id), "
            "       COALESCE(ps.name, 'product#' || cps.product_and_service_id) "
            "FROM customer_product_and_services cps "
            "LEFT JOIN customers cust ON cust.id = cps.customer_id "
            "LEFT JOIN product_and_services ps ON ps.id = cps.product_and_service_id "
            "WHERE cps.sheet_column_id IS NULL"
        )
    ).fetchall()

    plans: list[_Plan] = []
    for cps_id, product_and_service_id, customer_name, product_name in rows:
        mapping = old_mappings.get(product_and_service_id)
        plans.append(
            _Plan(
                cps_id=cps_id,
                customer_name=customer_name,
                product_name=product_name,
                sheet_column_id=mapping[0] if mapping else None,
                column_name=mapping[1] if mapping else None,
            )
        )
    return plans


def _print_report(plans: list[_Plan]) -> None:
    resolved = [p for p in plans if p.sheet_column_id is not None]
    unresolved = [p for p in plans if p.sheet_column_id is None]

    print(f"Found {len(plans)} customer-service row(s) with no sheet column set.\n")

    if resolved:
        print(f"Will backfill {len(resolved)} row(s) from the old product-level mapping:")
        for p in resolved:
            print(f"  {p.customer_name} / {p.product_name} -> \"{p.column_name}\"")
        print()

    if unresolved:
        print(f"{len(unresolved)} row(s) have no old mapping to copy — left unresolved, fix by hand:")
        for p in unresolved:
            print(f"  {p.customer_name} / {p.product_name}")
        print()


def _apply(db, plans: list[_Plan]) -> None:
    applied = 0
    for p in [p for p in plans if p.sheet_column_id is not None]:
        try:
            result = db.execute(
                text(
                    "UPDATE customer_product_and_services "
                    "SET sheet_column_id = :col_id "
                    "WHERE id = :cps_id AND sheet_column_id IS NULL"
                ),
                {"col_id": p.sheet_column_id, "cps_id": p.cps_id},
            )
            db.commit()
            if result.rowcount:  # 0 = already handled or gone since discovery
                applied += 1
        except Exception as e:  # noqa: BLE001 — report and keep going, one row must not block the rest
            db.rollback()
            print(f"ERROR applying {p.customer_name} / {p.product_name}: {e}")

    print(f"\nApplied {applied} of {sum(1 for p in plans if p.sheet_column_id is not None)} resolvable row(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        plans = _discover(db)
        _print_report(plans)

        if not args.apply:
            print("Dry run only — no changes written. Re-run with --apply once this looks right.")
            return

        _apply(db, plans)
    finally:
        db.close()


if __name__ == "__main__":
    main()
