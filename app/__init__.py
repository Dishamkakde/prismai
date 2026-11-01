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

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///prismai.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16777216))

    # Mail config
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Ensure upload folders exist
    uploads_base = app.config['UPLOAD_FOLDER']
    for folder in ['avatars', 'documents', 'research', 'misc', 'gallery']:
        os.makedirs(os.path.join(uploads_base, folder), exist_ok=True)

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.portal import portal_bp
    from app.routes.admin import admin_bp
    from app.routes.projects import projects_bp
    from app.routes.tasks import tasks_bp
    from app.routes.research import research_bp
    from app.routes.meetings import meetings_bp
    from app.routes.reports import reports_bp
    from app.routes.announcements import announcements_bp
    from app.routes.documents import documents_bp
    from app.routes.achievements import achievements_bp
    from app.routes.gallery import gallery_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(portal_bp, url_prefix='/portal')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(projects_bp, url_prefix='/portal/projects')
    app.register_blueprint(tasks_bp, url_prefix='/portal/tasks')
    app.register_blueprint(research_bp, url_prefix='/portal/research')
    app.register_blueprint(meetings_bp, url_prefix='/portal/meetings')
    app.register_blueprint(reports_bp, url_prefix='/portal/reports')
    app.register_blueprint(announcements_bp, url_prefix='/portal/announcements')
    app.register_blueprint(documents_bp, url_prefix='/portal/documents')
    app.register_blueprint(achievements_bp, url_prefix='/portal/achievements')
    app.register_blueprint(gallery_bp, url_prefix='/gallery')

    return app
