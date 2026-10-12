#!/usr/bin/env python3
"""
Reorder every customer's service rows (and so their invoice lines) to the
standard SKU order below. Products not in the list keep their current
relative order, after all listed ones; several rows of the same product
(different columns / centres) also keep their current relative order.

Usage (from backend/):
    python scripts/set_service_order.py --database-url postgresql+psycopg2://...   # dry run
    python scripts/set_service_order.py --database-url ... --apply
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import selectinload, sessionmaker

import app.models  # noqa: F401
from app.models.customer import Customer
from app.models.customer_product_and_service import CustomerProductAndService

# Exact ProductAndService names, in invoice order. (Matched case-insensitively.)
SKU_ORDER = [
    "Olivia AI Complete Bookings B0001",
    "Olivia AI - Provisional bookings B0001",
    "Olivia AI - Walk-in Call handling Charges B0001",
    "Non Appointment Call Handling Charges B0002",
    "Olivia Call Forwards to reception B0002",
    "E-Referral Transmission Charges B0003",
    "E-Referral Greeting SMS Charges B0003",
    "E-Referral Manual SMS Charges B0003",
    "Olivia Assist - Bookings via customer portal",
    "Olivia Specialist Portal Booking B0001",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--apply", action="store_true", help="Write the new order (default: dry run).")
    args = parser.parse_args()

    rank = {name.strip().lower(): i for i, name in enumerate(SKU_ORDER)}
    db = sessionmaker(bind=create_engine(args.database_url))()
    try:
        names_in_use = {
            cps.product_and_service.name.strip().lower()
            for cps in db.query(CustomerProductAndService).options(
                selectinload(CustomerProductAndService.product_and_service)
            )
        }
        for name in SKU_ORDER:
            if name.strip().lower() not in names_in_use:
                print(f"WARNING: '{name}' is not used by any customer (renamed in QuickBooks?)")

        changed = 0
        customers = db.query(Customer).options(
            selectinload(Customer.customer_services).selectinload(CustomerProductAndService.product_and_service)
        ).order_by(Customer.display_name).all()
        for cust in customers:
            rows = list(cust.customer_services)  # current order: position, id
            ordered = sorted(
                rows, key=lambda r: rank.get(r.product_and_service.name.strip().lower(), len(SKU_ORDER))
            )
            if [r.id for r in ordered] == [r.id for r in rows] and all(
                r.position == i for i, r in enumerate(ordered)
            ):
                continue
            changed += 1
            print(f"\n{cust.display_name}")
            for i, r in enumerate(ordered):
                r.position = i
                print(f"  {i + 1}. {r.product_and_service.name}")

        print(f"\n{changed} of {len(customers)} customer(s) reordered.")
        if args.apply:
            db.commit()
            print("Applied.")
        else:
            db.rollback()
            print("Dry run only — re-run with --apply to save.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
