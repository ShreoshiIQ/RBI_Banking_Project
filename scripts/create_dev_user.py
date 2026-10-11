import getpass

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.user import UserRecord
from regintel.security.passwords import hash_password


ALLOWED_ROLES = {
    "viewer",
    "admin",
    "compliance_officer",
}


def main():
    username = input("Username: ").strip()
    role = input(
        "Role (viewer/admin/compliance_officer): "
    ).strip()

    if not username:
        raise ValueError("Username is required")

    if role not in ALLOWED_ROLES:
        raise ValueError("Invalid role")

    password = getpass.getpass("Password: ")

    if len(password) < 12:
        raise ValueError(
            "Password must contain at least 12 characters"
        )

    with SessionLocal() as db:
        existing = db.scalar(
            select(UserRecord).where(
                UserRecord.username == username
            )
        )

        if existing is not None:
            raise ValueError("Username already exists")

        user = UserRecord(
            username=username,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(
            f"Created user ID {user.id}, "
            f"username={user.username}, role={user.role}"
        )


if __name__ == "__main__":
    main()
