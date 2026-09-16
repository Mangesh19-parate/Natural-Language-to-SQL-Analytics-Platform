from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.config import settings
from app.models.auth import User, Role
from app.models.policy import DataPolicy
from app.schemas.auth import (
    UserLogin,
    Token,
    TokenRefreshRequest,
    UserOut,
    UserCreate,
    RoleOut,
    AuthLoginResponse,
    UserProfile,
)
from app.schemas.common import StandardResponse
from app.services.auth_service import (
    AuthService,
    get_current_user,
    require_roles,
)

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post("/login", response_model=StandardResponse[AuthLoginResponse])
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates a user via email and password, issuing standard JWT access and refresh tokens (REQ-AUTH-01).
    """
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not AuthService.verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    role_name = user.role.role_name if user.role else "viewer"
    token_claims = {
        "sub": str(user.user_id),
        "user_id": user.user_id,
        "email": user.email,
        "role_name": role_name,
        "role_id": user.role_id,
    }

    access_token = AuthService.create_access_token(data=token_claims)
    refresh_token = AuthService.create_refresh_token(data=token_claims)

    user_out = UserOut(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        role_id=user.role_id,
        role_name=role_name,
        is_active=user.is_active,
    )

    return StandardResponse(
        success=True,
        message="Login successful",
        data=AuthLoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_out,
        ),
    )


@router.post("/refresh", response_model=StandardResponse[Token])
def refresh_token(request: TokenRefreshRequest, db: Session = Depends(get_db)):
    """
    Refreshes an access token using a valid refresh token.
    """
    payload = AuthService.decode_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub") or payload.get("user_id")
    user = db.query(User).filter(User.user_id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with refresh token is not found or inactive",
        )

    role_name = user.role.role_name if user.role else "viewer"
    token_claims = {
        "sub": str(user.user_id),
        "user_id": user.user_id,
        "email": user.email,
        "role_name": role_name,
        "role_id": user.role_id,
    }

    new_access_token = AuthService.create_access_token(data=token_claims)
    return StandardResponse(
        success=True,
        message="Token refreshed successfully",
        data=Token(
            access_token=new_access_token,
            refresh_token=request.refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


@router.get("/me", response_model=StandardResponse[UserProfile])
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns authenticated user profile, assigned role, and effective policy permissions summary.
    """
    role_name = current_user.role.role_name if current_user.role else "viewer"
    user_out = UserOut(
        user_id=current_user.user_id,
        full_name=current_user.full_name,
        email=current_user.email,
        role_id=current_user.role_id,
        role_name=role_name,
        is_active=current_user.is_active,
    )
    role_out = RoleOut(role_id=current_user.role.role_id, role_name=role_name) if current_user.role else None

    # Summarize active policies for the role
    policies = (
        db.query(DataPolicy)
        .filter(DataPolicy.role_id == current_user.role_id)
        .all()
        if current_user.role_id
        else []
    )
    perm_summary = {
        "accessible_tables": list(set(p.table_name for p in policies if p.access_level != "denied")),
        "aggregate_enabled_tables": list(set(p.table_name for p in policies if p.aggregate_allowed)),
        "row_filter_count": sum(1 for p in policies if p.row_filter_sql),
        "total_policy_rules": len(policies),
    }

    return StandardResponse(
        success=True,
        message="User profile retrieved",
        data=UserProfile(
            user=user_out,
            role=role_out,
            permissions_summary=perm_summary,
        ),
    )


@router.get("/roles", response_model=StandardResponse[List[RoleOut]])
def list_roles(db: Session = Depends(get_db)):
    """
    Lists all available system roles (admin, analyst, viewer).
    """
    roles = db.query(Role).all()
    # Seed default roles if not yet in DB
    if not roles:
        default_roles = [Role(role_name="admin"), Role(role_name="analyst"), Role(role_name="viewer")]
        db.add_all(default_roles)
        db.commit()
        roles = db.query(Role).all()

    return StandardResponse(
        success=True,
        message="Roles retrieved",
        data=[RoleOut.model_validate(r) for r in roles],
    )


@router.get("/users", response_model=StandardResponse[List[UserOut]])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists all users in the system.
    """
    users = db.query(User).all()
    out = []
    for u in users:
        role_name = u.role.role_name if u.role else "viewer"
        out.append(
            UserOut(
                user_id=u.user_id,
                full_name=u.full_name,
                email=u.email,
                role_id=u.role_id,
                role_name=role_name,
                is_active=u.is_active,
            )
        )
    return StandardResponse(
        success=True,
        message="Users retrieved",
        data=out,
    )


@router.post("/register", response_model=StandardResponse[UserOut])
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Creates a new user with hashed password.
    Always assigns the lowest-privilege 'viewer' role to public registrations (REQ-AUTH-01 / Rule R0).
    """
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Strictly assign 'viewer' role for all public self-registrations (never allow self-escalation)
    viewer_role = db.query(Role).filter(Role.role_name == "viewer").first()
    assigned_role_id = viewer_role.role_id if viewer_role else 3

    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        password_hash=AuthService.get_password_hash(user_data.password),
        role_id=assigned_role_id,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    role_name = new_user.role.role_name if new_user.role else "viewer"
    return StandardResponse(
        success=True,
        message="User registered successfully",
        data=UserOut(
            user_id=new_user.user_id,
            full_name=new_user.full_name,
            email=new_user.email,
            role_id=new_user.role_id,
            role_name=role_name,
            is_active=new_user.is_active,
        ),
    )


@router.put("/users/{user_id}/role", response_model=StandardResponse[UserOut])
def update_user_role(
    user_id: int,
    role_id: int,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Admin-only endpoint to assign or change a user's role (REQ-AUTH-01).
    """
    target_user = db.query(User).filter(User.user_id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    target_role = db.query(Role).filter(Role.role_id == role_id).first()
    if not target_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found",
        )

    target_user.role_id = role_id
    db.commit()
    db.refresh(target_user)

    role_name = target_user.role.role_name if target_user.role else "viewer"
    return StandardResponse(
        success=True,
        message=f"User role updated to '{role_name}' successfully",
        data=UserOut(
            user_id=target_user.user_id,
            full_name=target_user.full_name,
            email=target_user.email,
            role_id=target_user.role_id,
            role_name=role_name,
            is_active=target_user.is_active,
        ),
    )

