from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    admin = User.query.filter_by(email='admin@gmail.com').first()
    if admin:
        admin.set_password('admin12345')
        db.session.commit()
        print("Password reset!")
        print(f"  Email:    admin@gmail.com")
        print(f"  Password: admin12345")
