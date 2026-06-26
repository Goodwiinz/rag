import argparse
import os
import sys
import bcrypt
from urllib.parse import urlparse

# Set up path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy import create_engine, text
from backend.src.core.config import settings


def _force_dev_db_url(db_url: str) -> str:
    """Replace only the database name segment with the dev database, never the hostname."""
    parsed = urlparse(db_url)
    if parsed.path and parsed.path.lstrip("/"):
        new_path = "/multimodal_rag_dev"
        return db_url[: len(db_url) - len(parsed.path)] + new_path
    return db_url


def reset_password(
    email: str, new_password: str, reactivate: bool = False, dev: bool = False
) -> bool:
    print(f"Resetting password for {email}...")
    if reactivate:
        print("⚠️  --reactivate set: account will be marked is_active=true")

    # Generate bcrypt hash directly
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), salt).decode("utf-8")

    db_url = settings.DATABASE_URL
    if dev:
        print(f"Forcing dev database (multimodal_rag_dev) instead of {db_url}")
        db_url = _force_dev_db_url(db_url)

    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(
            text("SELECT id, is_active FROM users WHERE email = :email"),
            {"email": email},
        )
        user = result.fetchone()

        if not user:
            print(f"User {email} not found!")
            return False

        if reactivate:
            conn.execute(
                text(
                    "UPDATE users SET password_hash = :pwd, is_active = true WHERE email = :email"
                ),
                {"pwd": hashed_password, "email": email},
            )
        else:
            # Preserve the existing is_active value (do not silently re-activate)
            conn.execute(
                text("UPDATE users SET password_hash = :pwd WHERE email = :email"),
                {"pwd": hashed_password, "email": email},
            )
        conn.commit()
        print(f"Password updated successfully for {email}")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset a user's password (bypasses the auth layer)."
    )
    parser.add_argument("--email", required=True, help="Email of the account to reset")
    parser.add_argument(
        "--password",
        required=True,
        help="New password (passed via CLI; prefer --password-env)",
    )
    parser.add_argument(
        "--password-env",
        help="Environment variable name holding the new password (preferred over --password)",
    )
    parser.add_argument(
        "--reactivate",
        action="store_true",
        help="Also set is_active=true (off by default)",
    )
    parser.add_argument(
        "--dev", action="store_true", help="Force the dev database (multimodal_rag_dev)"
    )
    args = parser.parse_args()

    new_password = (
        os.environ.get(args.password_env) if args.password_env else args.password
    )
    if not new_password:
        sys.exit(
            "Error: a new password must be provided via --password or --password-env"
        )

    success = reset_password(
        args.email, new_password, reactivate=args.reactivate, dev=args.dev
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
