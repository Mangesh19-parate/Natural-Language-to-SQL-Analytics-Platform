from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.db.base import Base, BusinessBase

# Metadata DB Engine & Session
metadata_db_url = settings.get_effective_metadata_db_url()
metadata_connect_args = {"check_same_thread": False} if "sqlite" in metadata_db_url else {}
metadata_engine = create_engine(metadata_db_url, connect_args=metadata_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=metadata_engine)

# Business DB Engine & Session (Readonly by default)
business_db_url = settings.get_effective_business_db_url(admin=False)
business_connect_args = {"check_same_thread": False} if "sqlite" in business_db_url else {}
business_engine = create_engine(business_db_url, connect_args=business_connect_args, pool_pre_ping=True)
BusinessSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=business_engine)

# Business Admin DB Engine (for schema migration and seed scripts)
business_admin_db_url = settings.get_effective_business_db_url(admin=True)
business_admin_engine = create_engine(business_admin_db_url, connect_args=business_connect_args, pool_pre_ping=True)
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
