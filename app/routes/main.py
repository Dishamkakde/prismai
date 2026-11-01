from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models import Project, MemberProfile, Announcement, ProjectStatus, MemberApplication
from app import db
from datetime import datetime

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    total_members = MemberProfile.query.count()
    total_projects = Project.query.count()
    completed_projects = Project.query.filter_by(status=ProjectStatus.COMPLETED).count()
    pinned_announcements = Announcement.query.filter_by(is_pinned=True, is_active=True).order_by(Announcement.created_at.desc()).limit(3).all()
    return render_template('main/index.html',
                           total_members=total_members,
                           total_projects=total_projects,
                           completed_projects=completed_projects,
                           announcements=pinned_announcements)


@main_bp.route('/about')
def about():
    return render_template('main/about.html')


@main_bp.route('/events')
def events():
    return render_template('main/events.html')


@main_bp.route('/team')
def team():
    profiles = MemberProfile.query.join(MemberProfile.user).filter_by(is_active=True).all()
    return render_template('main/team.html', profiles=profiles)


@main_bp.route('/projects')
def projects():
    public_projects = Project.query.filter_by(visibility='public').all()
    return render_template('main/projects.html', projects=public_projects)


@main_bp.route('/contact')
def contact():
    return render_template('main/contact.html')


@main_bp.route('/apply', methods=['GET', 'POST'])
def apply():
    """Public membership application form."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        # Prevent duplicate applications
        existing = MemberApplication.query.filter_by(email=email, status='pending').first()
        if existing:
            flash('An application with this email is already under review.', 'warning')
            return render_template('main/apply.html')

        from app.models import User
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists. Please sign in.', 'warning')
            return redirect(url_for('auth.signin'))

        app_obj = MemberApplication(
            full_name=request.form.get('full_name', '').strip(),
            email=email,
            usn=request.form.get('usn', '').strip(),
            phone=request.form.get('phone', '').strip(),
            branch=request.form.get('branch', '').strip(),
            academic_year=request.form.get('academic_year', '').strip(),
            department=request.form.get('department', '').strip(),
            designation=request.form.get('designation', 'Member').strip(),
            reason=request.form.get('reason', '').strip(),
        )
        db.session.add(app_obj)
        db.session.commit()

        # Notify admins
        from app.models import User, Role
        from app.utils import create_notification
        admins = User.query.filter(User.role.in_([Role.ADMIN, Role.RESEARCH_HEAD])).all()
        for admin in admins:
            create_notification(admin.id, 'New Membership Application',
                f'{app_obj.full_name} applied to join PRISM AI.',
                'announcement', url_for('admin.applications'))

        flash('Your application has been submitted! You will be notified at your email once reviewed.', 'success')
        return redirect(url_for('main.index'))

    return render_template('main/apply.html')


@main_bp.app_errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@main_bp.app_errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@main_bp.app_errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500
