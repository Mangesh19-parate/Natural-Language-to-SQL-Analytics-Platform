from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role_name: Optional[str] = None
    role_id: Optional[int] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RoleOut(BaseModel):
    role_id: int
    role_name: str

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role_id: Optional[int] = None
    is_active: bool = True


class UserOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AuthLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserProfile(BaseModel):
    user: UserOut
    role: Optional[RoleOut] = None
    permissions_summary: Dict[str, Any] = {}

