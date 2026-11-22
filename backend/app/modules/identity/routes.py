from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import Conflict, Unauthorized
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.modules.identity.models import Role, User
from app.modules.identity.schemas import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["identity"])


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise Unauthorized("Bearer access token required")
    user_id = decode_access_token(authorization.removeprefix("Bearer ").strip())
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise Unauthorized("Inactive or unknown user")
    return user


@router.post("/register", response_model=MeResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> MeResponse:
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise Conflict("A user with this email already exists")
    farmer = db.scalar(select(Role).where(Role.name == "farmer"))
    if farmer is None:
        raise RuntimeError("Role seed data is missing")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        locale=payload.locale,
        roles=[farmer],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        locale=user.locale,
        roles=[r.value for r in user.role_names],
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise Unauthorized("Invalid email or password")
    if not user.is_active:
        raise Unauthorized("User account is inactive")
    token, expires_at = create_access_token(user.id, [r.value for r in user.role_names])
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return TokenResponse(access_token=token, expires_at=expires_at)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(current_user)) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        locale=user.locale,
        roles=[r.value for r in user.role_names],
    )
