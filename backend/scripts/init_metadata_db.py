import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal, metadata_engine
from app.db.base import Base
from app.models.auth import Role, User
from app.models.policy import DataSource
from app.services.auth_service import AuthService


def init_metadata_database():
    """
    Initializes metadata database with default roles, admin user, and data sources (Task T-03).
    """
    print("--- [T-03] Initializing Metadata Database ---")
    Base.metadata.create_all(bind=metadata_engine)
    db: Session = SessionLocal()

    try:
        # 1. Seed Roles
        roles = ["admin", "analyst", "viewer"]
        role_map = {}
        for r_name in roles:
            existing = db.query(Role).filter(Role.role_name == r_name).first()
            if not existing:
                r = Role(role_name=r_name)
                db.add(r)
                db.flush()
                role_map[r_name] = r
            else:
                role_map[r_name] = existing
        print("[OK] Verified default roles (admin, analyst, viewer).")

        # 2. Seed Default Standard Users
        seed_users = [
            ("System Administrator", "admin@trustengine.ai", "AdminSecurePassword123!", "admin"),
            ("System Administrator Legacy", "admin@example.com", "AdminSecurePassword123!", "admin"),
            ("Senior Data Analyst", "analyst@trustengine.ai", "AnalystSecurePassword123!", "analyst"),
            ("Business Viewer", "viewer@trustengine.ai", "ViewerSecurePassword123!", "viewer"),
        ]

        for full_name, email, raw_pw, r_name in seed_users:
            u = db.query(User).filter(User.email == email).first()
            pw_hash = AuthService.get_password_hash(raw_pw)
            if not u:
                u = User(
                    full_name=full_name,
                    email=email,
                    password_hash=pw_hash,
                    role_id=role_map[r_name].role_id,
                    is_active=True
                )
                db.add(u)
                db.flush()
                print(f"[OK] Created initial user: {email} (role: {r_name})")
            else:
                u.password_hash = pw_hash
                u.role_id = role_map[r_name].role_id
                u.is_active = True
                db.flush()

        # 3. Seed Default Business Data Source
        default_ds = db.query(DataSource).filter(DataSource.name == "Primary Enterprise DB").first()
        if not default_ds:
            default_ds = DataSource(
                name="Primary Enterprise DB",
                db_type="postgresql",
                host="localhost",
                port=5432,
                database_name="sql_assistant_business",
                connection_role="readonly_app_user",
                secret_ref="env:BUSINESS_DB_URL",
                is_active=True
            )
            db.add(default_ds)
            db.flush()
            print("[OK] Created default data source reference: Primary Enterprise DB")

        db.commit()
        print("--- [T-03] Metadata Database Initialization Complete ---")

    except Exception as e:
        db.rollback()
        print(f"Error initializing metadata: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    init_metadata_database()
