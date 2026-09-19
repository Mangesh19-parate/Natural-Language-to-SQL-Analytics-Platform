from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.db.base import Base, BusinessBase

# Metadata DB Engine & Session (Calibrated Connection Pool)
metadata_db_url = settings.get_effective_metadata_db_url()
metadata_connect_args = {"check_same_thread": False} if "sqlite" in metadata_db_url else {}
metadata_pool_kwargs = {}
if "sqlite" not in metadata_db_url:
    metadata_pool_kwargs = {
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 30.0,
        "pool_recycle": 1800,
    }

metadata_engine = create_engine(
    metadata_db_url,
    connect_args=metadata_connect_args,
    pool_pre_ping=True,
    **metadata_pool_kwargs
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=metadata_engine)

# Business DB Engine & Session (Readonly by default, Dedicated Isolated Pool)
business_db_url = settings.get_effective_business_db_url(admin=False)
business_connect_args = {"check_same_thread": False} if "sqlite" in business_db_url else {}
business_pool_kwargs = {}
if "sqlite" not in business_db_url:
    business_pool_kwargs = {
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 30.0,
        "pool_recycle": 1800,
    }

business_engine = create_engine(
    business_db_url,
    connect_args=business_connect_args,
    pool_pre_ping=True,
    **business_pool_kwargs
)
BusinessSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=business_engine)

# Business Admin DB Engine (for schema migration and seed scripts)
business_admin_db_url = settings.get_effective_business_db_url(admin=True)
business_admin_engine = create_engine(
    business_admin_db_url,
    connect_args=business_connect_args,
    pool_pre_ping=True,
)
BusinessAdminSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=business_admin_engine)


def get_db():
    """FastAPI Dependency for Metadata DB session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_business_db():
    """FastAPI Dependency for Business DB session (Readonly)."""
    db: Session = BusinessSessionLocal()
    try:
        yield db
    finally:
        db.close()
