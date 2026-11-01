import os
import uuid
from functools import wraps
from flask import abort, current_app
from flask_login import current_user
from app.models import Role, AuditLog
from app import db
from datetime import datetime, timezone
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
                      'png', 'jpg', 'jpeg', 'gif', 'zip', 'txt', 'csv', 'mp4'}

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS


def save_file(file, subfolder='misc'):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, filename))
        return f"{subfolder}/{filename}"
    return None


def save_avatar(file):
    if file and allowed_image(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"avatar_{uuid.uuid4().hex}.{ext}"
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'avatars')
        os.makedirs(upload_path, exist_ok=True)
        from PIL import Image
        img = Image.open(file)
        img.thumbnail((300, 300))
        img.save(os.path.join(upload_path, filename))
        return f"avatars/{filename}"
    return None


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def lead_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_project_lead():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def log_action(action, resource_type=None, resource_id=None, details=None):
    from flask import request
    log = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=request.remote_addr,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(log)
    db.session.commit()


def create_notification(user_id, title, message, notif_type, link=None):
    from app.models import Notification
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notif_type=notif_type,
        link=link
    )
    db.session.add(notif)
    db.session.commit()


def generate_member_id():
    import random
    import string
    while True:
        mid = 'PRA' + ''.join(random.choices(string.digits, k=5))
        from app.models import User
        if not User.query.filter_by(member_id=mid).first():
            return mid


def generate_project_id():
    import random
    import string
    while True:
        pid = 'PRJ' + ''.join(random.choices(string.digits, k=4))
        from app.models import Project
        if not Project.query.filter_by(project_id=pid).first():
            return pid
