import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.auth import User, Role
from app.schemas.auth import TokenData, UserOut

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer(auto_error=False)

# In-memory revocation cache for rotated/revoked tokens
_REVOKED_TOKENS = set()


class AuthService:
    """
    Central Authentication and JWT Token Management service (REQ-AUTH-01 / Rule R0).
    Provides robust password verification, token issuance, server-side RBAC validation,
    and centralized resource ownership checks.
    """

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain password against the stored bcrypt hash securely (Fail-Closed)."""
        if not hashed_password or not plain_password:
            return False
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            # Fail closed immediately if hash is malformed or verification fails
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hashes a plain password using bcrypt (Fail-Closed)."""
        if not password:
            raise ValueError("Password cannot be empty")
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Encodes user claims into a signed JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "type": "access", "jti": os.urandom(16).hex()})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Encodes user claims into a signed JWT refresh token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh", "jti": os.urandom(16).hex()})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def is_token_revoked(token: str, jti: Optional[str] = None, db: Optional[Session] = None) -> bool:
        """Checks if a token or JTI is revoked in fast memory or persistent store."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if (jti and jti in _REVOKED_TOKENS) or token_hash in _REVOKED_TOKENS:
            return True
        if db is not None:
            try:
                from app.models.auth import RevokedToken
                query = db.query(RevokedToken)
                if jti:
                    match = query.filter((RevokedToken.jti == jti) | (RevokedToken.token_hash == token_hash)).first()
                else:
                    match = query.filter(RevokedToken.token_hash == token_hash).first()
                if match:
                    if jti:
                        _REVOKED_TOKENS.add(jti)
                    _REVOKED_TOKENS.add(token_hash)
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def decode_token(token: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """Decodes and validates a JWT token signature, expiration, and revocation status."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            jti = payload.get("jti")
            if AuthService.is_token_revoked(token, jti, db):
                return None
            return payload
        except JWTError:
            return None

    @staticmethod
    def revoke_token(token: str, db: Optional[Session] = None) -> bool:
        """Revokes a JWT token by adding its jti or token hash to revocation store."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        jti = None
        exp_dt = None
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False}
            )
            jti = payload.get("jti")
            exp_ts = payload.get("exp")
            if exp_ts:
                exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
        except Exception:
            pass

        if jti:
            _REVOKED_TOKENS.add(jti)
        _REVOKED_TOKENS.add(token_hash)

        if db is not None:
            try:
                from app.models.auth import RevokedToken
                revoked_entry = RevokedToken(
                    jti=jti,
                    token_hash=token_hash,
                    expires_at=exp_dt,
                )
                db.add(revoked_entry)
                db.commit()
            except Exception:
                db.rollback()
        return True


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Extracts the authenticated user if Bearer token is provided, or returns None."""
    if not credentials or not credentials.credentials:
        return None

    payload = AuthService.decode_token(credentials.credentials, db=db)
    if not payload:
        return None

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        return None

    user = db.query(User).filter(User.user_id == int(user_id)).first()
    return user



def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Enforces strict JWT authentication (raises 401 if missing or invalid)."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = AuthService.decode_token(credentials.credentials, db=db)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.user_id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return user


def require_roles(allowed_roles: List[str]):
    """
    Role-based Authorization Dependency.
    Enforces server-side role check independent of client UI assertions (REQ-AUTH-01 / Rule R0).
    """
    def role_checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        user_role_name = current_user.role.role_name.lower() if current_user.role else "viewer"
        allowed_normalized = [r.lower() for r in allowed_roles]
        if user_role_name not in allowed_normalized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role in {allowed_roles}, but current user role is '{user_role_name}'.",
            )
        return current_user

    return role_checker


def get_effective_role_id(current_user: User, requested_role_id: Optional[int] = None) -> int:
    """
    Derives the effective role ID strictly on the server side.
    If the caller is an Admin, they are allowed to simulate other roles (e.g. for Policy Matrix/Labs).
    For all non-admin users, their assigned database role_id is strictly enforced and client requests are ignored.
    """
    user_role_name = current_user.role.role_name.lower() if current_user.role else "viewer"
    if user_role_name == "admin" and requested_role_id is not None:
        return requested_role_id
    if current_user.role_id is not None:
        return current_user.role_id
    return 3  # Fallback to viewer role if unassigned


def authorize_resource_access(
    resource_owner_id: Optional[int],
    current_user: User,
    resource_type: str = "resource",
    action: str = "access",
) -> None:
    """
    Centralized Resource Ownership & Least Privilege Authorization Gate (SEC-RESOURCE-OWNERSHIP).
    Enforces that non-admin callers can only view/rerun/download their own resources.
    Admins are permitted cross-user access for governance/auditing.
    """
    user_role_name = current_user.role.role_name.lower() if current_user.role else "viewer"
    if user_role_name == "admin":
        return

    if resource_owner_id is None or current_user.user_id != resource_owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You do not have permission to {action} this {resource_type}.",
        )


