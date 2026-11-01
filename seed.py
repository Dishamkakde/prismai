"""
PRISM AI — Database initialisation script.
Run ONCE on a fresh setup: python seed.py

Creates only the admin account.
NO demo/test data is ever added.
All real member data comes through the Admin invitation workflow.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, MemberProfile, Role
from app.utils import generate_member_id
from datetime import date, datetime

app = create_app()

with app.app_context():
    # Only drop & recreate if DB is truly empty or doesn't exist
    db.create_all()

    existing_admin = User.query.filter_by(role=Role.ADMIN).first()
    if existing_admin:
        print("=" * 50)
        print("  Database already initialised.")
        print(f"  Admin account: {existing_admin.email}")
        print("  No changes made.")
        print("=" * 50)
    else:
        member_id = generate_member_id()
        admin = User(
            member_id=member_id,
            email='admin@prismai.edu',   # Change this to your real email
            role=Role.ADMIN,
            is_active=True,
            is_approved=True,
            last_login=datetime.utcnow()
        )
        admin.set_password('ChangeMe@2025')   # CHANGE after first login
        db.session.add(admin)
        db.session.flush()

        profile = MemberProfile(
            user_id=admin.id,
            full_name='PRISM Admin',
            department='Research & Projects',
            designation='Research Head',
            joined_date=date.today(),
            membership_status='Active'
        )
        db.session.add(profile)
        db.session.commit()

        print("=" * 50)
        print("  PRISM AI — Database initialised!")
        print("=" * 50)
        print(f"  Admin ID    : {member_id}")
        print(f"  Admin Email : admin@prismai.edu")
        print(f"  Password    : ChangeMe@2025")
        print("=" * 50)
        print("  IMPORTANT: Change the password immediately")
        print("  after your first login via Settings.")
        print("=" * 50)
