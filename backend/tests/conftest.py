import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base, BusinessBase
from app.models import (
    Role, User, DataSource, DataPolicy, SemanticCatalog,
    Department, Employee, Customer, Product, Order, Sale
)

from app.main import app
from app.db.session import get_db
from app.services.auth_service import get_current_user, AuthService

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_engine():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    BusinessBase.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    BusinessBase.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    connection = test_engine.connect()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    connection.close()


@pytest.fixture(scope="function", autouse=True)
def setup_test_db(db_session):
    """Sets default DB dependency override for integration tests."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


def create_test_auth_headers(db_session, role_name: str = "admin", user_id: int = 1, email: str = None) -> dict:
    """Helper to seed role/user in test DB and return valid Bearer auth header dict."""
    if email is None:
        email = f"test_{role_name}_{user_id}@trustengine.ai"

    role = db_session.query(Role).filter(Role.role_name == role_name).first()
    if not role:
        role = Role(role_name=role_name)
        db_session.add(role)
        db_session.flush()

    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            full_name=f"Test {role_name.capitalize()}",
            email=email,
            password_hash=AuthService.get_password_hash("TestPass123!"),
            role_id=role.role_id,
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()

    token = AuthService.create_access_token({
        "sub": str(user.user_id),
        "user_id": user.user_id,
        "email": user.email,
        "role_name": role_name,
        "role_id": user.role_id,
    })
    return {"Authorization": f"Bearer {token}"}



