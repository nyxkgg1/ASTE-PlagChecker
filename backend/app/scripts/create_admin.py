from getpass import getpass

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.user import User, Role, UserRole


def create_admin():
    db = SessionLocal()

    try:
        username = input("Admin username: ").strip()
        email = input("Admin email: ").strip()
        full_name = input("Admin full name: ").strip()

        password = getpass("Admin password: ")
        confirm_password = getpass("Confirm password: ")

        if password != confirm_password:
            print("Passwords do not match.")
            return

        if len(password) < 8:
            print("Password must contain at least 8 characters.")
            return

        existing_user = db.query(User).filter(
            (User.username == username) |
            (User.email == email)
        ).first()

        if existing_user:
            print("A user with this username or email already exists.")
            return

        admin_role = db.query(Role).filter(
            Role.role_name == "ADMIN"
        ).first()

        if not admin_role:
            print("ADMIN role does not exist.")
            print("Create the roles first.")
            return

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            status="ACTIVE",
        )

        db.add(user)
        db.flush()

        user_role = UserRole(
            user_id=user.id,
            role_id=admin_role.id,
            assigned_by=None,
        )

        db.add(user_role)
        db.commit()

        print()
        print("Admin user created successfully.")
        print(f"Username: {username}")
        print(f"User ID: {user.id}")

    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()