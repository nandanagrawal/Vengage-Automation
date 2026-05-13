from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, Token, UserLogin, UserProfileUpdate, UserRegister, UserResponse
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter()


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


@router.post("/auth/login", response_model=Token)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == str(body.email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    token = create_access_token(user.id, user.email, user.role.value)
    return Token(access_token=token)


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
