import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

app = create_app()

# Auto-create tables and seed admin on first start
with app.app_context():
    db.create_all()
    try:
        from app.models import User, Role, MemberProfile
        from app.utils import generate_member_id
        from datetime import date, datetime
        if not User.query.filter_by(role=Role.ADMIN).first():
            mid = generate_member_id()
            admin = User(
                member_id=mid,
                email=os.environ.get('ADMIN_EMAIL', 'admin@prismai.edu'),
                role=Role.ADMIN,
                is_active=True,
                is_approved=True,
                last_login=datetime.utcnow()
            )
            admin.set_password(os.environ.get('ADMIN_PASSWORD', 'PrismAdmin@2025'))
            db.session.add(admin)
            db.session.flush()
            db.session.add(MemberProfile(
                user_id=admin.id,
                full_name='PRISM Admin',
                department='Research & Projects',
                designation='Research Head',
                joined_date=date.today(),
                membership_status='Active'
            ))
            db.session.commit()
    except Exception as e:
        print(f"Seed warning: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
