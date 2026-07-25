"""
Creates an admin/moderator account. Deliberately not exposed as an API
endpoint — run this directly on the server (or via `docker compose exec`)
by someone who already has infrastructure access. There is no public
admin self-registration path anywhere in this app, by design.

Usage:
    python scripts/create_admin.py <username>
    (will prompt for a password, not taken as a CLI arg to avoid it
    landing in shell history)
"""

import sys
import getpass

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.admin import AdminUser
from app.services import auth_service


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_admin.py <username>")
        sys.exit(1)

    username = sys.argv[1]
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords did not match.")
        sys.exit(1)
    if len(password) < 12:
        print("Use a longer password for an admin account — 12+ characters minimum.")
        sys.exit(1)

    db = SessionLocal()
    if db.query(AdminUser).filter_by(username=username).first():
        print(f"Admin '{username}' already exists.")
        sys.exit(1)

    admin = AdminUser(username=username, password_hash=auth_service.hash_password(password))
    db.add(admin)
    db.commit()
    print(f"Admin account '{username}' created.")


if __name__ == "__main__":
    main()
