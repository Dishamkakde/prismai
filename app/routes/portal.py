from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import (Project, Task, Announcement, Meeting, WeeklyReport,
                        Achievement, Notification, TaskStatus, ProjectStatus,
                        MemberProfile, ChangeRequest)
from app.utils import save_avatar, log_action, create_notification
from datetime import datetime, timezone, date
import json

portal_bp = Blueprint('portal', __name__)


@portal_bp.route('/dashboard')
@login_required
def dashboard():
    profile = current_user.profile
    if not profile:
        flash('Please complete your profile.', 'warning')

    # Stats
    my_projects = current_user.projects
    active_projects = [p for p in my_projects if p.status not in [ProjectStatus.COMPLETED, ProjectStatus.ON_HOLD]]
    completed_projects = [p for p in my_projects if p.status == ProjectStatus.COMPLETED]

    my_tasks = Task.query.filter_by(assignee_id=current_user.id).all()
    pending_tasks = [t for t in my_tasks if t.status in [TaskStatus.TODO, TaskStatus.IN_PROGRESS]]
    completed_tasks = [t for t in my_tasks if t.status == TaskStatus.COMPLETED]
    overdue_tasks = [t for t in my_tasks if t.is_overdue()]

    # Recent announcements
    announcements = Announcement.query.filter_by(is_active=True).order_by(
        Announcement.created_at.desc()).limit(5).all()

    # Upcoming meetings
    now = datetime.utcnow()
    upcoming_meetings = Meeting.query.filter(
        Meeting.participants.any(id=current_user.id),
        Meeting.meeting_date >= now
    ).order_by(Meeting.meeting_date).limit(3).all()

    # Unread notifications count
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

    # Recent notifications
    recent_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()).limit(8).all()

    points = profile.contribution_points if profile else 0
    achievements_count = Achievement.query.filter_by(user_id=current_user.id, is_verified=True).count()

    return render_template('portal/dashboard.html',
                           profile=profile,
                           active_projects=active_projects,
                           completed_projects=completed_projects,
                           my_projects=my_projects,
                           pending_tasks=pending_tasks,
                           completed_tasks=completed_tasks,
                           overdue_tasks=overdue_tasks,
                           announcements=announcements,
                           upcoming_meetings=upcoming_meetings,
                           unread_count=unread_count,
                           recent_notifications=recent_notifications,
                           points=points,
                           achievements_count=achievements_count)


@portal_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile = current_user.profile
    if not profile:
        profile = MemberProfile(user_id=current_user.id, full_name='New Member')
        db.session.add(profile)
        db.session.commit()

    if request.method == 'POST':
        # Admins save directly; members submit change requests for approval
        if current_user.is_admin():
            # Admin can edit directly
            profile.bio = request.form.get('bio', '').strip()
            profile.technical_skills = request.form.get('technical_skills', '').strip()
            profile.areas_of_interest = request.form.get('areas_of_interest', '').strip()
            profile.github_url = request.form.get('github_url', '').strip()
            profile.linkedin_url = request.form.get('linkedin_url', '').strip()
            profile.portfolio_url = request.form.get('portfolio_url', '').strip()
            profile.phone = request.form.get('phone', '').strip()

            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    saved = save_avatar(file)
                    if saved:
                        profile.profile_picture = saved

            profile.updated_at = datetime.utcnow()
            db.session.commit()
            log_action('update_profile', 'profile', profile.id)
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('portal.profile'))
        else:
            # Members: build change request
            field_changes = {}
            new_values = {
                'bio': request.form.get('bio', '').strip(),
                'technical_skills': request.form.get('technical_skills', '').strip(),
                'areas_of_interest': request.form.get('areas_of_interest', '').strip(),
                'github_url': request.form.get('github_url', '').strip(),
                'linkedin_url': request.form.get('linkedin_url', '').strip(),
                'portfolio_url': request.form.get('portfolio_url', '').strip(),
                'phone': request.form.get('phone', '').strip(),
            }

            for field, new_val in new_values.items():
                old_val = getattr(profile, field, '') or ''
                if new_val != old_val:
                    field_changes[field] = {'old': old_val, 'new': new_val}

            # Avatar upload — save to temp, reference in change request
            has_avatar = False
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    saved = save_avatar(file)
                    if saved:
                        field_changes['profile_picture'] = {'old': profile.profile_picture or '', 'new': saved}
                        has_avatar = True

            if not field_changes:
                flash('No changes detected to submit.', 'info')
                return redirect(url_for('portal.profile'))

            description = request.form.get('change_description', '').strip()
            if not description:
                description = 'Profile update request'

            cr = ChangeRequest(
                user_id=current_user.id,
                target_type='profile',
                target_id=profile.id,
                action='update',
                field_changes=json.dumps(field_changes),
                description=description,
                status='pending'
            )
            db.session.add(cr)
            db.session.commit()

            # Notify all admins
            from app.models import User, Role
            admins = User.query.filter(User.role.in_([Role.ADMIN, Role.RESEARCH_HEAD])).all()
            for admin in admins:
                create_notification(admin.id, 'Change Request Submitted',
                    f'{current_user.profile.full_name if current_user.profile else "A member"} requested a profile update.',
                    'announcement', url_for('admin.change_requests'))

            log_action('submit_change_request', 'change_request', cr.id)
            flash('Your profile changes have been submitted for admin approval. You will be notified once reviewed.', 'info')
            return redirect(url_for('portal.profile'))

    achievements = Achievement.query.filter_by(user_id=current_user.id, is_verified=True).all()
    return render_template('portal/profile.html', profile=profile, achievements=achievements)


@portal_bp.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()).all()
    # Mark all as read
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('portal/notifications.html', notifications=notifs)


@portal_bp.route('/notifications/mark-read/<int:notif_id>')
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    notif.is_read = True
    db.session.commit()
    return redirect(url_for('portal.notifications'))


@portal_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            if not current_user.check_password(current_pw):
                flash('Current password is incorrect.', 'danger')
            elif len(new_pw) < 8:
                flash('New password must be at least 8 characters.', 'danger')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'danger')
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                log_action('change_password', 'user', current_user.id)
                flash('Password changed successfully.', 'success')
    return render_template('portal/settings.html')
