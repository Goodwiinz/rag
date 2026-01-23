#!/usr/bin/env python3
"""
Reset admin user password
"""
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.database import get_db
from core.security import get_password_hash
from models.user import User

def reset_admin_password():
    """Reset admin user password to REDACTED"""
    db = next(get_db())

    try:
        # Find admin user
        admin_user = db.query(User).filter(User.email == "admin@multimodal-rag.com").first()

        if not admin_user:
            print("❌ Admin user not found!")
            return False

        # Generate new password hash
        new_password = "REDACTED"
        new_hash = get_password_hash(new_password)

        # Update password
        admin_user.password_hash = new_hash
        db.commit()

        print(f"✅ Admin password reset successfully!")
        print(f"   Email: {admin_user.email}")
        print(f"   New Password: {new_password}")
        print(f"   Hash Length: {len(new_hash)}")

        # Test password verification
        from core.security import verify_password
        if verify_password(new_password, new_hash):
            print("✅ Password verification test passed!")
        else:
            print("❌ Password verification test failed!")

        return True

    except Exception as e:
        print(f"❌ Error resetting password: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Resetting admin user password...")
    reset_admin_password()