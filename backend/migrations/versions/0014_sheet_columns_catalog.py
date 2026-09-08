"""Sheet column catalog — product_column_mappings now references a curated
SheetColumn instead of storing free-text column_header, so the mapping UI can
offer a dropdown and enforce one-column-per-product at the DB level.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sheet_columns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_sheet_columns_name"),
    )
    op.create_index("ix_sheet_columns_name", "sheet_columns", ["name"])

    op.add_column(
        "product_column_mappings", sa.Column("sheet_column_id", sa.Integer(), nullable=True)
    )

    # Backfill: any existing free-text column_header becomes a SheetColumn row,
    # and product_column_mappings points at it. No-op on a fresh DB (empty table).
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id, column_header FROM product_column_mappings")
    ).fetchall()
    for row in existing:
        header = row.column_header.strip()
        sc_id = bind.execute(
            sa.text("SELECT id FROM sheet_columns WHERE name = :name"), {"name": header}
        ).scalar()
        if sc_id is None:
            sc_id = bind.execute(
                sa.text(
                    "INSERT INTO sheet_columns (name, created_at) VALUES (:name, now()) RETURNING id"
                ),
                {"name": header},
            ).scalar()
        bind.execute(
            sa.text("UPDATE product_column_mappings SET sheet_column_id = :sc_id WHERE id = :id"),
            {"sc_id": sc_id, "id": row.id},
        )

    op.alter_column("product_column_mappings", "sheet_column_id", nullable=False)
    op.create_unique_constraint(
        "uq_product_column_mappings_sheet_column_id", "product_column_mappings", ["sheet_column_id"]
    )
    op.create_index(
        "ix_product_column_mappings_sheet_column_id", "product_column_mappings", ["sheet_column_id"]
    )
    op.create_foreign_key(
        "fk_product_column_mappings_sheet_column_id",
        "product_column_mappings", "sheet_columns",
        ["sheet_column_id"], ["id"], ondelete="RESTRICT",
    )
    op.drop_column("product_column_mappings", "column_header")


def downgrade() -> None:
    op.add_column(
        "product_column_mappings", sa.Column("column_header", sa.String(500), nullable=True)
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE product_column_mappings pcm "
            "SET column_header = sc.name "
            "FROM sheet_columns sc WHERE sc.id = pcm.sheet_column_id"
        )
    )
    op.alter_column("product_column_mappings", "column_header", nullable=False)

    op.drop_constraint(
        "fk_product_column_mappings_sheet_column_id", "product_column_mappings", type_="foreignkey"
    )
    op.drop_index("ix_product_column_mappings_sheet_column_id", table_name="product_column_mappings")
    op.drop_constraint(
        "uq_product_column_mappings_sheet_column_id", "product_column_mappings", type_="unique"
    )
    op.drop_column("product_column_mappings", "sheet_column_id")

    op.drop_index("ix_sheet_columns_name", table_name="sheet_columns")
    op.drop_table("sheet_columns")
