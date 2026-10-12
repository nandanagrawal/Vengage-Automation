from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    BackupCodesRegenerateRequest,
    BackupCodesResponse,
    ChangePasswordRequest,
    LoginResponse,
    Token,
    TwoFactorLoginSuccess,
    TwoFactorSetupConfirm,
    TwoFactorVerify,
    UserLogin,
    UserProfileUpdate,
    UserRegister,
    UserResponse,
)
from app.services import two_factor_service
from app.services.auth_service import (
    create_access_token,
    create_pending_2fa_token,
    decode_pending_2fa_token,
    hash_password,
    verify_password,
)

router = APIRouter()

_TRUSTED_DEVICE_COOKIE = "vengage_trusted_device"
_TRUSTED_DEVICE_COOKIE_PATH = "/api/v1/auth"


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: UserRegister,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Admin-only: create a new user account."""
    if db.query(User).filter(User.email == str(body.email)).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=str(body.email),
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/register/first", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_first_admin(body: UserRegister, db: Session = Depends(get_db)):
    """Bootstrap: create the very first admin user — blocked once any user exists."""
    if db.query(User).count() > 0:
        raise HTTPException(status_code=403, detail="Use /auth/register (admin required) after bootstrap")
    if body.role.value != "admin":
        raise HTTPException(status_code=400, detail="First user must be admin")
    user = User(
        email=str(body.email),
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _set_trusted_device_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _TRUSTED_DEVICE_COOKIE,
        token,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        max_age=settings.TRUSTED_DEVICE_DAYS * 24 * 3600,
        path=_TRUSTED_DEVICE_COOKIE_PATH,
    )


@router.post("/auth/login", response_model=LoginResponse)
def login(body: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == str(body.email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    device_token = request.cookies.get(_TRUSTED_DEVICE_COOKIE)
    if two_factor_service.is_trusted_device(db, user.id, device_token):
        token = create_access_token(user.id, user.email, user.role.value)
        return LoginResponse(status="success", access_token=token)

    pending = create_pending_2fa_token(user.id)
    if not user.totp_enabled:
        qr_data_uri, manual_key = two_factor_service.start_enrollment(db, user)
        return LoginResponse(
            status="setup_required",
            pending_token=pending,
            qr_code_data_uri=qr_data_uri,
            manual_entry_key=manual_key,
        )
    return LoginResponse(status="verify_required", pending_token=pending)


def _user_from_pending_token(db: Session, pending_token: str) -> User:
    try:
        user_id = decode_pending_2fa_token(pending_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired login session — please log in again")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired login session — please log in again")
    return user


@router.post("/auth/2fa/setup/confirm", response_model=TwoFactorLoginSuccess)
def two_factor_setup_confirm(
    body: TwoFactorSetupConfirm,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = _user_from_pending_token(db, body.pending_token)
    try:
        backup_codes = two_factor_service.confirm_enrollment(db, user, body.code)
    except ValueError:
        raise HTTPException(status_code=400, detail="Incorrect code — check your authenticator app and try again")

    if body.remember_device:
        device_token = two_factor_service.issue_trusted_device_token(db, user, request.headers.get("user-agent"))
        _set_trusted_device_cookie(response, device_token)

    access_token = create_access_token(user.id, user.email, user.role.value)
    return TwoFactorLoginSuccess(access_token=access_token, backup_codes=backup_codes)


@router.post("/auth/2fa/verify", response_model=TwoFactorLoginSuccess)
def two_factor_verify(
    body: TwoFactorVerify,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = _user_from_pending_token(db, body.pending_token)
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not set up for this account yet")
    if not two_factor_service.verify_login_code(db, user, body.code):
        raise HTTPException(status_code=400, detail="Incorrect code")

    if body.remember_device:
        device_token = two_factor_service.issue_trusted_device_token(db, user, request.headers.get("user-agent"))
        _set_trusted_device_cookie(response, device_token)

    access_token = create_access_token(user.id, user.email, user.role.value)
    return TwoFactorLoginSuccess(access_token=access_token)


@router.post("/auth/2fa/backup-codes/regenerate", response_model=BackupCodesResponse)
def regenerate_backup_codes(
    body: BackupCodesRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        codes = two_factor_service.regenerate_backup_codes(db, current_user, body.code)
    except ValueError:
        raise HTTPException(status_code=400, detail="Incorrect code")
    return BackupCodesResponse(backup_codes=codes)


@router.post("/auth/users/{user_id}/reset-2fa", response_model=UserResponse)
def admin_reset_2fa(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Lost-device-and-backup-codes recovery path: clears 2FA state for a
    user so they're walked through enrollment again on their next login."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    two_factor_service.reset_2fa(db, user)
    db.refresh(user)
    return user


@router.get("/auth/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/auth/me", response_model=UserResponse)
def update_profile(
    body: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.full_name = body.full_name
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/auth/me/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(body.new_password)
    db.add(current_user)
    db.commit()
    return {"ok": True}
