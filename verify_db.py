from app import create_app, db
from app.models import User, Invitation

app = create_app()
with app.app_context():
    users = User.query.all()
    invites = Invitation.query.all()
    print("=" * 40)
    print(f"Users in DB: {len(users)}")
    for u in users:
        p = u.profile
        name = p.full_name if p else "no profile"
        print(f"  {u.email} | {u.role} | {name} | approved={u.is_approved}")
    print(f"Invitations: {len(invites)}")
    print("=" * 40)
    if len(users) == 1 and users[0].role == 'admin':
        print("Database is clean. Only admin exists.")
    print("=" * 40)
