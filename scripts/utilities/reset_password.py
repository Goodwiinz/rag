import sys
import os
import bcrypt
# Set up path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy import create_engine, text
from backend.src.core.config import settings

def reset_password(email, new_password):
    print(f"Resetting password for {email}...")
    
    # Generate bcrypt hash directly
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
    
    # Force connection to dev DB
    db_url = settings.DATABASE_URL
    if "multimodal_rag_dev" not in db_url:
        print(f"Warning: Configured DB is {db_url}, forcing multimodal_rag_dev")
        db_url = db_url.replace("multimodal_rag", "multimodal_rag_dev")
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})
        user = result.fetchone()
        
        if not user:
            print(f"User {email} not found!")
            return False
            
        # Update password
        conn.execute(
            text("UPDATE users SET password_hash = :pwd, is_active = true WHERE email = :email"),
            {"pwd": hashed_password, "email": email}
        )
        conn.commit()
        print(f"Password updated successfully for {email}")
        return True

if __name__ == "__main__":
    success = reset_password("admin@multimodal-rag.com", "REDACTED")
    if not success:
        sys.exit(1)
