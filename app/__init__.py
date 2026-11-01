from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
mail = Mail()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # ── Database ─────────────────────────────────
    # On Render, use /tmp for writable SQLite path
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        # Default: store db next to app folder so it persists across restarts
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, 'prismai.db')
        db_url = f'sqlite:///{db_path}'

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production-prismai-2025')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16777216))

    # ── Upload folder ─────────────────────────────
    # Use absolute path so it works on any deployment
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_upload = os.path.join(base_dir, 'app', 'static', 'uploads')
    uploads_base = os.environ.get('UPLOAD_FOLDER', default_upload)
    app.config['UPLOAD_FOLDER'] = uploads_base

    # ── Mail ──────────────────────────────────────
    app.config['MAIL_SERVER']   = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT']     = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS']  = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

    # ── Extensions ────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # ── Create upload folders ─────────────────────
    for folder in ['avatars', 'documents', 'research', 'misc', 'gallery', 'submissions', 'certificates']:
        try:
            os.makedirs(os.path.join(uploads_base, folder), exist_ok=True)
        except OSError:
            pass

    # ── Blueprints ────────────────────────────────
    from app.routes.main          import main_bp
    from app.routes.auth          import auth_bp
    from app.routes.portal        import portal_bp
    from app.routes.admin         import admin_bp
    from app.routes.projects      import projects_bp
    from app.routes.tasks         import tasks_bp
    from app.routes.research      import research_bp
    from app.routes.meetings      import meetings_bp
    from app.routes.reports       import reports_bp
    from app.routes.announcements import announcements_bp
    from app.routes.documents     import documents_bp
    from app.routes.achievements  import achievements_bp
    from app.routes.gallery       import gallery_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,          url_prefix='/auth')
    app.register_blueprint(portal_bp,        url_prefix='/portal')
    app.register_blueprint(admin_bp,         url_prefix='/admin')
    app.register_blueprint(projects_bp,      url_prefix='/portal/projects')
    app.register_blueprint(tasks_bp,         url_prefix='/portal/tasks')
    app.register_blueprint(research_bp,      url_prefix='/portal/research')
    app.register_blueprint(meetings_bp,      url_prefix='/portal/meetings')
    app.register_blueprint(reports_bp,       url_prefix='/portal/reports')
    app.register_blueprint(announcements_bp, url_prefix='/portal/announcements')
    app.register_blueprint(documents_bp,     url_prefix='/portal/documents')
    app.register_blueprint(achievements_bp,  url_prefix='/portal/achievements')
    app.register_blueprint(gallery_bp,       url_prefix='/gallery')

    return app
