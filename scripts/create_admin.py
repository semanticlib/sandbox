#!/usr/bin/env python3
"""
CLI script to create an admin user.

Usage:
    python scripts/create_admin.py
    
The script will prompt for username and password interactively.
Password input is hidden for security.
"""
import sys
import os
import getpass

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal, engine, Base
from core.models import AdminUser
from core.security import get_password_hash

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)


def create_admin(username: str, password: str):
    """Create an admin user in the database."""
    db = SessionLocal()
    
    try:
        # Check if user already exists
        existing = db.query(AdminUser).filter(AdminUser.username == username).first()
        if existing:
            print(f"\n❌ Error: Username '{username}' already exists!")
            return False
        
        # Validate password length
        if len(password) < 6:
            print("\n❌ Error: Password must be at least 6 characters long!")
            return False
        
        # Create new admin user
        admin = AdminUser(
            username=username,
            password_hash=get_password_hash(password),
            is_active=True,
            is_first_login=False
        )
        
        db.add(admin)
        db.commit()
        
        print(f"\n✅ Admin user '{username}' created successfully!")
        print(f"   You can now login at: http://localhost:8000/login")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        return False
    
    finally:
        db.close()


def main():
    print("=" * 50)
    print("  Create Admin User")
    print("=" * 50)
    print()
    
    # Prompt for username
    while True:
        username = input("Username: ").strip()
        
        if not username:
            print("❌ Username cannot be empty. Please try again.")
            continue
        
        if not username.replace("-", "").replace("_", "").isalnum():
            print("❌ Username must be alphanumeric (hyphens and underscores allowed).")
            continue
        
        break
    
    # Prompt for password (hidden)
    while True:
        password = getpass.getpass("Password: ")
        
        if len(password) < 6:
            print("❌ Password must be at least 6 characters. Please try again.")
            continue
        
        # Confirm password
        password_confirm = getpass.getpass("Confirm Password: ")
        
        if password != password_confirm:
            print("❌ Passwords do not match. Please try again.")
            continue
        
        break
    
    print()
    print(f"Creating admin user '{username}'...")
    
    success = create_admin(username, password)
    
    if success:
        print()
        print("Setup complete! You can now start the application and login.")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
