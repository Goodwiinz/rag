#!/usr/bin/env python
"""Test token verification.

The JWT to verify is provided via the TEST_JWT environment variable or the
``--token`` CLI argument — it is never hardcoded in source control.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
os.chdir(os.path.join(os.getcwd(), "backend"))

from src.core.config import settings
from src.core.security import verify_token


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a JWT against the app secret.")
    parser.add_argument("--token", help="JWT to verify (alternatively set TEST_JWT)")
    args = parser.parse_args()

    token = args.token or os.environ.get("TEST_JWT")
    if not token:
        sys.exit(
            "Error: provide a token via --token or the TEST_JWT environment variable"
        )

    print(f"JWT_ALGORITHM: {settings.JWT_ALGORITHM}")

    result = verify_token(token)
    print(f"\nverify_token result: {result}")

    if result:
        print(f"  user_id: {result.user_id}")
        print(f"  email: {result.email}")
        print(f"  role: {result.role}")
    else:
        print("  Token verification FAILED")
        from jose import jwt, JWTError

        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
            print(f"  Manual decode worked: {payload}")
        except JWTError as e:
            print(f"  Manual decode error: {e}")


if __name__ == "__main__":
    main()
