import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.auth import Role
from app.models.policy import DataSource, DataPolicy


def seed_demo_policies():
    """Seeds baseline demo policies for Admin and Analyst roles."""
    db: Session = SessionLocal()
    try:
        ds = db.query(DataSource).first()
        admin_role = db.query(Role).filter(Role.role_name == "admin").first()
        analyst_role = db.query(Role).filter(Role.role_name == "analyst").first()
        viewer_role = db.query(Role).filter(Role.role_name == "viewer").first()

        if not (ds and admin_role and analyst_role):
            print("Required entities not found.")
            return

        tables = ["departments", "employees", "customers", "products", "orders", "sales"]

        # Admin: Full Read Access to all tables
        for tbl in tables:
            existing = db.query(DataPolicy).filter(
                DataPolicy.role_id == admin_role.role_id,
                DataPolicy.data_source_id == ds.data_source_id,
                DataPolicy.table_name == tbl,
                DataPolicy.column_name == None
            ).first()
            if not existing:
                db.add(DataPolicy(
                    role_id=admin_role.role_id,
                    data_source_id=ds.data_source_id,
                    table_name=tbl,
                    column_name=None,
                    access_level="read",
                    aggregate_allowed=True
                ))

        # Analyst: Read Access to products, orders, sales
        analyst_tables = ["products", "orders", "sales"]
        for tbl in analyst_tables:
            existing = db.query(DataPolicy).filter(
                DataPolicy.role_id == analyst_role.role_id,
                DataPolicy.data_source_id == ds.data_source_id,
                DataPolicy.table_name == tbl,
                DataPolicy.column_name == None
            ).first()
            if not existing:
                db.add(DataPolicy(
                    role_id=analyst_role.role_id,
                    data_source_id=ds.data_source_id,
                    table_name=tbl,
                    column_name=None,
                    access_level="read",
                    aggregate_allowed=False
                ))

        # Viewer: NO DATA POLICY ROWS (Intentionally left empty for fail-closed verification)
        db.commit()
        print("[OK] Demo role policies seeded: Admin (6 tables), Analyst (3 tables), Viewer (0 tables - Fail Closed).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_policies()
