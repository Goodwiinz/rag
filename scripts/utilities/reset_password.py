"""Operator script to reset a user's password.

This script bypasses the application auth layer and writes directly to the
users table — use only as a break-glass tool. Credentials and target email
must be supplied as CLI arguments; nothing is hardcoded (issue #375).
"""

import argparse
import getpass
import logging
import os
import sys

import bcrypt

# Set up path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from backend.src.core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)


def _resolve_db_url() -> str:
    """Return DATABASE_URL, preferring an explicit override for safety."""
    override = os.environ.get("RESET_PASSWORD_DB_URL")
    if override:
        return override
    return settings.DATABASE_URL


def reset_password(email: str, new_password: str, *, reactivate: bool = False) -> bool:
    """Reset the password for `email`. Returns False if the user is missing."""
    logger.info("Resetting password for %s", email)

    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), salt).decode("utf-8")

    engine = create_engine(_resolve_db_url())
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT id, is_active FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()

        if not user:
            logger.error("User %s not found", email)
            return False

        if reactivate:
            conn.execute(
                text(
                    "UPDATE users SET password_hash = :pwd, is_active = true "
                    "WHERE email = :email"
                ),
                {"pwd": hashed_password, "email": email},
            )
            logger.warning("Reactivated and reset password for %s", email)
        else:
            # Don't silently re-enable disabled accounts; surface that to the operator.
            if not user.is_active:
                logger.error(
                    "Account %s is disabled. Re-run with --reactivate if this is intended.",
                    email,
                )
                return False
            conn.execute(
                text("UPDATE users SET password_hash = :pwd WHERE email = :email"),
                {"pwd": hashed_password, "email": email},
            )
            logger.info("Password updated for %s", email)

        conn.commit()
        return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Target user email")
    parser.add_argument(
        "--password",
        help=(
            "New password. If omitted, you will be prompted (recommended)."
        ),
    )
    parser.add_argument(
        "--reactivate",
        action="store_true",
        help=(
            "Re-activate the account if it has been disabled. Off by default to "
            "avoid silently restoring suspended accounts."
        ),
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()

    password = args.password or getpass.getpass("New password: ")
    if not password:
        logger.error("Password cannot be empty")
        return 2

    return 0 if reset_password(args.email, password, reactivate=args.reactivate) else 1


if __name__ == "__main__":
    sys.exit(main())
