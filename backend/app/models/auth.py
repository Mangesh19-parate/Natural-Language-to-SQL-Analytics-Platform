from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), unique=True, nullable=False)  # 'admin', 'analyst', 'viewer'

    users = relationship("User", back_populates="role")
    policies = relationship("DataPolicy", back_populates="role")


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    role = relationship("Role", back_populates="users")
    sessions = relationship("SessionModel", back_populates="user")
    queries = relationship("QueryHistory", back_populates="user")
    reports = relationship("Report", back_populates="user")
    feedbacks = relationship("Feedback", back_populates="user")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, index=True, nullable=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    revoked_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)

