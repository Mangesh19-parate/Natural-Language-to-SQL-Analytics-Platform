import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base, BusinessBase
from app.models import (
    Role, User, DataSource, DataPolicy, SemanticCatalog,
    Department, Employee, Customer, Product, Order, Sale
)

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    BusinessBase.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    BusinessBase.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
