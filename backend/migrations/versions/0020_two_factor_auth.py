"""Mandatory TOTP two-factor authentication for all users.

- users.totp_secret: Fernet-encrypted TOTP secret (see
  app/services/totp_crypto.py). Set as soon as enrollment starts; only
  meaningful once totp_enabled is true.
- users.totp_enabled: false until the first code is verified, so a
  half-finished enrollment never counts as "has 2FA" — see
  app/services/auth_service.py's create_pending_2fa_token flow.
- user_backup_codes: one-time recovery codes, bcrypt-hashed like passwords
  (never stored or logged in plaintext after issuance).
- user_trusted_devices: "remember this browser for 7 days" — token_hash is
  SHA-256, not bcrypt, since the token itself is a 32-byte random secret
  (ample entropy on its own) and this needs a fast indexed exact-match
  lookup on every login, which bcrypt's per-row salt makes impossible.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("totp_secret", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    op.create_table(
        "user_backup_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=200), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_foreign_key(
        "fk_user_backup_codes_user_id",
        "user_backup_codes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_user_backup_codes_user_id", "user_backup_codes", ["user_id"]
    )

    op.create_table(
        "user_trusted_devices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_user_trusted_devices_user_id",
        "user_trusted_devices",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_user_trusted_devices_user_id", "user_trusted_devices", ["user_id"]
    )
    op.create_unique_constraint(
        "uq_user_trusted_devices_token_hash", "user_trusted_devices", ["token_hash"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_user_trusted_devices_token_hash", "user_trusted_devices", type_="unique"
    )
    op.drop_index("ix_user_trusted_devices_user_id", table_name="user_trusted_devices")
    op.drop_constraint(
        "fk_user_trusted_devices_user_id", "user_trusted_devices", type_="foreignkey"
    )
    op.drop_table("user_trusted_devices")

    op.drop_index("ix_user_backup_codes_user_id", table_name="user_backup_codes")
    op.drop_constraint(
        "fk_user_backup_codes_user_id", "user_backup_codes", type_="foreignkey"
    )
    op.drop_table("user_backup_codes")

    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
