"""
PRISM AI — Entry point.
  Local:      python run.py
  Production: gunicorn run:app
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

app = create_app()

def _init_db():
    """Create tables and seed admin on first run."""
    with app.app_context():
        db.create_all()
        from app.models import User, Role
        if not User.query.filter_by(role=Role.ADMIN).first():
            from app.models import MemberProfile
            from app.utils import generate_member_id
            from datetime import date, datetime
            mid = generate_member_id()
            admin = User(
                member_id=mid,
                email=os.environ.get('ADMIN_EMAIL', 'admin@prismai.edu'),
                role=Role.ADMIN,
                is_active=True,
                is_approved=True,
                last_login=datetime.utcnow()
            )
            admin.set_password(os.environ.get('ADMIN_PASSWORD', 'ChangeMe@2025'))
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
            print(f"  Admin created: {admin.email}")

_init_db()

if __name__ == '__main__':
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║   PRISM AI  —  http://127.0.0.1:5000 ║")
    print("  ╚══════════════════════════════════════╝\n")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
