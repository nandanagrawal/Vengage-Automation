from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


class UserProfileUpdate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    totp_enabled: bool


# ── Two-factor authentication ───────────────────────────────────────────────

class LoginResponse(BaseModel):
    """What POST /auth/login returns — exactly one of three shapes.

    - status == "success": password alone was enough (a valid
      remember-this-device cookie was presented) — access_token is set,
      everything else is None.
    - status == "setup_required": correct password, but this user has never
      completed 2FA enrollment — pending_token/qr_code_data_uri/
      manual_entry_key are set, access_token is None.
    - status == "verify_required": correct password, 2FA already enabled —
      only pending_token is set.
    """

    status: Literal["success", "setup_required", "verify_required"]
    access_token: str | None = None
    token_type: str = "bearer"
    pending_token: str | None = None
    qr_code_data_uri: str | None = None
    manual_entry_key: str | None = None


class TwoFactorSetupConfirm(BaseModel):
    pending_token: str
    code: str = Field(min_length=6, max_length=8)
    remember_device: bool = False


class TwoFactorVerify(BaseModel):
    pending_token: str
    # Either a 6-digit TOTP code or an 8-character backup code.
    code: str = Field(min_length=6, max_length=8)
    remember_device: bool = False


class TwoFactorLoginSuccess(BaseModel):
    status: Literal["success"] = "success"
    access_token: str
    token_type: str = "bearer"
    # Only present on the response from /auth/2fa/setup/confirm — shown to
    # the user exactly once, never retrievable again afterward.
    backup_codes: list[str] | None = None


class BackupCodesRegenerateRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class BackupCodesResponse(BaseModel):
    backup_codes: list[str]
