from app import create_app, db
from app.models import User, Role

app = create_app()
with app.app_context():
    users = User.query.all()
    print(f"\nTotal users: {len(users)}")
    for u in users:
        p = u.profile
        print(f"\n  Email:    {u.email}")
        print(f"  Role:     {u.role}")
        print(f"  Approved: {u.is_approved}")
        print(f"  Active:   {u.is_active}")
        print(f"  Name:     {p.full_name if p else 'no profile'}")
