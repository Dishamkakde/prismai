from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Announcement, User
from app.utils import log_action, create_notification
from datetime import datetime, timezone

announcements_bp = Blueprint('announcements', __name__)

CATEGORIES = ['General', 'Research Update', 'Project Update', 'Meeting',
              'Opportunity', 'Competition', 'Deadline', 'Achievement']


@announcements_bp.route('/')
@login_required
def list_announcements():
    category = request.args.get('category', '')
    query = Announcement.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    announcements = query.order_by(Announcement.is_pinned.desc(),
                                   Announcement.created_at.desc()).all()
    return render_template('portal/announcements/list.html',
                           announcements=announcements, categories=CATEGORIES,
                           selected_category=category)


@announcements_bp.route('/<int:ann_id>')
@login_required
def view_announcement(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    if not ann.is_active and not current_user.is_admin():
        abort(404)
    return render_template('portal/announcements/view.html', announcement=ann)


@announcements_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_announcement():
    if not current_user.is_admin():
        abort(403)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('portal/announcements/create.html', categories=CATEGORIES)

        expires_str = request.form.get('expires_at')
        expires_at = datetime.strptime(expires_str, '%Y-%m-%d') if expires_str else None

        ann = Announcement(
            title=title,
            content=content,
            category=request.form.get('category', 'General'),
            priority=request.form.get('priority', 'Normal'),
            target_department=request.form.get('target_department', '').strip() or None,
            is_pinned=request.form.get('is_pinned') == 'on',
            posted_by=current_user.id,
            expires_at=expires_at
        )
        db.session.add(ann)
        db.session.commit()

        # Notify all active users
        all_users = User.query.filter_by(is_active=True).all()
        for u in all_users:
            if u.id != current_user.id:
                create_notification(u.id, f'New Announcement: {title}',
                                    content[:100] + '...' if len(content) > 100 else content,
                                    'announcement', url_for('announcements.view_announcement', ann_id=ann.id))

        log_action('create_announcement', 'announcement', ann.id)
        flash('Announcement published.', 'success')
        return redirect(url_for('announcements.list_announcements'))

    return render_template('portal/announcements/create.html', categories=CATEGORIES)


@announcements_bp.route('/<int:ann_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_announcement(ann_id):
    if not current_user.is_admin():
        abort(403)
    ann = Announcement.query.get_or_404(ann_id)

    if request.method == 'POST':
        ann.title = request.form.get('title', ann.title).strip()
        ann.content = request.form.get('content', ann.content).strip()
        ann.category = request.form.get('category', ann.category)
        ann.priority = request.form.get('priority', ann.priority)
        ann.is_pinned = request.form.get('is_pinned') == 'on'
        ann.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('Announcement updated.', 'success')
        return redirect(url_for('announcements.view_announcement', ann_id=ann_id))

    return render_template('portal/announcements/edit.html', announcement=ann, categories=CATEGORIES)
