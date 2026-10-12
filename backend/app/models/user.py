import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    supervisor = "supervisor"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", native_enum=False), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Fernet-encrypted (app/services/totp_crypto.py); set as soon as
    # enrollment starts, only meaningful once totp_enabled is true.
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    # False until the first code is verified — a half-finished enrollment
    # (secret generated but never confirmed) never counts as "has 2FA".
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    backup_codes: Mapped[list["UserBackupCode"]] = relationship(
        "UserBackupCode", back_populates="user", cascade="all, delete-orphan"
    )
    trusted_devices: Mapped[list["UserTrustedDevice"]] = relationship(
        "UserTrustedDevice", back_populates="user", cascade="all, delete-orphan"
    )


class UserBackupCode(Base):
    """One-time 2FA recovery code — bcrypt-hashed like a password, since it's
    just as capable of authenticating someone as one is."""

    __tablename__ = "user_backup_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="backup_codes")


class UserTrustedDevice(Base):
    """"Remember this browser for 7 days" — token_hash is SHA-256 (not
    bcrypt): the raw token is already a 32-byte random secret with ample
    entropy on its own, and this needs a fast indexed exact-match lookup on
    every login, which bcrypt's per-row salt makes impossible."""

    __tablename__ = "user_trusted_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="trusted_devices")
