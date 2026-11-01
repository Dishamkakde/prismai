from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (User, MemberProfile, Project, Task, Invitation, Role,
                        Department, Achievement, Announcement, WeeklyReport,
                        AuditLog, Notification, TaskStatus, ProjectStatus)
from app.utils import admin_required, log_action, create_notification, generate_member_id
from datetime import datetime, timezone, timedelta, date
import csv
import io
from flask import Response

admin_bp = Blueprint('admin', __name__)


def require_admin():
    if not current_user.is_authenticated or not current_user.is_admin():
        abort(403)


@admin_bp.route('/dashboard')
@login_required
def dashboard():
    require_admin()

    # Overview stats
    total_members = User.query.count()
    active_members = User.query.filter_by(is_active=True).count()
    pending_approvals = User.query.filter_by(is_approved=False, is_active=True).count()
    total_projects = Project.query.count()
    ongoing_projects = Project.query.filter(
        Project.status.notin_([ProjectStatus.COMPLETED, ProjectStatus.ON_HOLD])
    ).count()
    completed_projects = Project.query.filter_by(status=ProjectStatus.COMPLETED).count()
    pending_tasks = Task.query.filter(
        Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS])
    ).count()
    today = date.today()
    overdue_tasks = Task.query.filter(
        Task.due_date < today,
        Task.status.notin_([TaskStatus.COMPLETED])
    ).count()
    week_start = today - timedelta(days=today.weekday())
    weekly_submissions = WeeklyReport.query.filter(
        WeeklyReport.submitted_at >= datetime.combine(week_start, datetime.min.time())
    ).count()

    # Recent activity
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()

    # Members per department
    from sqlalchemy import func
    dept_stats = db.session.query(
        MemberProfile.department, func.count(MemberProfile.id)
    ).group_by(MemberProfile.department).all()

    # Project status distribution
    status_stats = db.session.query(
        Project.status, func.count(Project.id)
    ).group_by(Project.status).all()

    return render_template('admin/dashboard.html',
                           total_members=total_members,
                           active_members=active_members,
                           pending_approvals=pending_approvals,
                           total_projects=total_projects,
                           ongoing_projects=ongoing_projects,
                           completed_projects=completed_projects,
                           pending_tasks=pending_tasks,
                           overdue_tasks=overdue_tasks,
                           weekly_submissions=weekly_submissions,
                           recent_logs=recent_logs,
                           dept_stats=dept_stats,
                           status_stats=status_stats)


@admin_bp.route('/members')
@login_required
def members():
    require_admin()
    users = User.query.join(MemberProfile, isouter=True).order_by(User.id).all()
    return render_template('admin/members/list.html', users=users)


@admin_bp.route('/members/pending')
@login_required
def pending_members():
    require_admin()
    pending = User.query.filter_by(is_approved=False, is_active=True).order_by(User.created_at.desc()).all()
    return render_template('admin/members/pending.html', pending=pending)


@admin_bp.route('/members/<int:user_id>/approve', methods=['POST'])
@login_required
def approve_member(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.is_admin():
        flash('Admin accounts do not need approval.', 'info')
        return redirect(url_for('admin.pending_members'))

    user.is_approved = True
    db.session.commit()
    create_notification(user.id, 'Account Approved!',
        'Your PRISM AI account has been approved. You can now sign in.',
        'announcement', url_for('auth.signin'))
    log_action('approve_member', 'user', user_id)
    flash(f'{user.profile.full_name if user.profile else user.email} has been approved.', 'success')
    return redirect(url_for('admin.pending_members'))


@admin_bp.route('/members/<int:user_id>/reject', methods=['POST'])
@login_required
def reject_member(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.is_admin():
        flash('Cannot reject an admin account.', 'danger')
        return redirect(url_for('admin.pending_members'))

    name = user.profile.full_name if user.profile else user.email
    user.is_active = False
    db.session.commit()
    log_action('reject_member', 'user', user_id)
    flash(f'{name} has been rejected and deactivated.', 'info')
    return redirect(url_for('admin.pending_members'))


@admin_bp.route('/members/invite', methods=['GET', 'POST'])
@login_required
def invite_member():
    require_admin()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', Role.MEMBER)
        department = request.form.get('department', '')

        if not email:
            flash('Email is required.', 'danger')
            return render_template('admin/members/invite.html')

        # Validate it looks like a Gmail address
        if not email.endswith('@gmail.com'):
            flash('Please use a Gmail address (@gmail.com).', 'danger')
            return render_template('admin/members/invite.html')

        if User.query.filter_by(email=email).first():
            flash('A user with this email already exists.', 'danger')
            return render_template('admin/members/invite.html')

        # Delete ALL existing invitations for this email (used or unused)
        # to avoid the UNIQUE constraint on invitations.email
        Invitation.query.filter_by(email=email).delete()
        db.session.flush()  # flush the delete before the insert

        token = Invitation.generate_token()
        expires = datetime.utcnow() + timedelta(days=7)
        invite = Invitation(
            email=email, token=token, role=role,
            department=department, invited_by=current_user.id,
            expires_at=expires
        )
        db.session.add(invite)
        db.session.commit()

        register_url = url_for('auth.register', token=token, _external=True)
        log_action('invite_member', 'invitation', invite.id, email)
        flash(f'Invitation created for {email}. Registration link: {register_url}', 'success')
        return redirect(url_for('admin.invitations'))

    roles = [Role.MEMBER, Role.PROJECT_LEAD, Role.RESEARCH_HEAD, Role.ADMIN]
    departments = [Department.RESEARCH, Department.WEBMASTER, Department.TECHNICAL,
                   Department.SOCIAL, Department.PR, Department.EVENTS]
    return render_template('admin/members/invite.html', roles=roles, departments=departments)


@admin_bp.route('/members/<int:user_id>')
@login_required
def member_detail(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    profile = user.profile
    tasks = Task.query.filter_by(assignee_id=user_id).all()
    reports = WeeklyReport.query.filter_by(user_id=user_id).order_by(WeeklyReport.week_start.desc()).limit(10).all()
    achievements = Achievement.query.filter_by(user_id=user_id).all()
    return render_template('admin/members/detail.html', user=user, profile=profile,
                           tasks=tasks, reports=reports, achievements=achievements)


@admin_bp.route('/members/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_member(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    profile = user.profile

    if request.method == 'POST':
        user.role = request.form.get('role', user.role)
        user.is_active = request.form.get('is_active') == 'on'

        if profile:
            profile.full_name = request.form.get('full_name', profile.full_name).strip()
            profile.usn = request.form.get('usn', profile.usn or '').strip()
            profile.branch = request.form.get('branch', profile.branch or '').strip()
            profile.academic_year = request.form.get('academic_year', profile.academic_year or '').strip()
            profile.department = request.form.get('department', profile.department or '').strip()
            profile.designation = request.form.get('designation', profile.designation or '').strip()
            profile.membership_status = request.form.get('membership_status', 'Active')
        
        db.session.commit()
        log_action('edit_member', 'user', user_id)
        flash('Member updated.', 'success')
        return redirect(url_for('admin.member_detail', user_id=user_id))

    roles = [Role.MEMBER, Role.PROJECT_LEAD, Role.RESEARCH_HEAD, Role.ADMIN]
    departments = [Department.RESEARCH, Department.WEBMASTER, Department.TECHNICAL,
                   Department.SOCIAL, Department.PR, Department.EVENTS]
    return render_template('admin/members/edit.html', user=user, profile=profile,
                           roles=roles, departments=departments)


@admin_bp.route('/members/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def toggle_member_active(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate yourself.', 'danger')
        return redirect(url_for('admin.members'))
    user.is_active = not user.is_active
    db.session.commit()
    state = 'activated' if user.is_active else 'deactivated'
    log_action(f'member_{state}', 'user', user_id)
    flash(f'Member {state}.', 'success')
    return redirect(url_for('admin.member_detail', user_id=user_id))


@admin_bp.route('/projects')
@login_required
def projects():
    require_admin()
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('admin/projects/list.html', projects=all_projects)


@admin_bp.route('/reports')
@login_required
def reports():
    require_admin()
    all_reports = WeeklyReport.query.order_by(WeeklyReport.submitted_at.desc()).all()
    return render_template('admin/reports.html', reports=all_reports)


@admin_bp.route('/achievements')
@login_required
def achievements():
    require_admin()
    pending = Achievement.query.filter_by(is_verified=False).order_by(Achievement.awarded_at.desc()).all()
    verified = Achievement.query.filter_by(is_verified=True).order_by(Achievement.awarded_at.desc()).all()
    return render_template('admin/achievements.html', pending=pending, verified=verified)


@admin_bp.route('/analytics')
@login_required
def analytics():
    require_admin()
    from sqlalchemy import func

    # Members per department
    dept_data = db.session.query(
        MemberProfile.department, func.count(MemberProfile.id)
    ).group_by(MemberProfile.department).all()

    # Tasks per status
    task_data = db.session.query(
        Task.status, func.count(Task.id)
    ).group_by(Task.status).all()

    # Projects per status
    proj_data = db.session.query(
        Project.status, func.count(Project.id)
    ).group_by(Project.status).all()

    # Top contributors
    top_contributors = MemberProfile.query.order_by(
        MemberProfile.contribution_points.desc()
    ).limit(10).all()

    # Report submission rates (last 4 weeks)
    from datetime import date, timedelta
    today = date.today()
    weekly_data = []
    for i in range(4):
        week_start = today - timedelta(weeks=i+1, days=today.weekday())
        week_end = week_start + timedelta(days=6)
        count = WeeklyReport.query.filter(
            WeeklyReport.week_start == week_start
        ).count()
        weekly_data.append({'week': week_start.strftime('%b %d'), 'count': count})

    return render_template('admin/analytics.html',
                           dept_data=dept_data,
                           task_data=task_data,
                           proj_data=proj_data,
                           top_contributors=top_contributors,
                           weekly_data=list(reversed(weekly_data)))


@admin_bp.route('/export/members')
@login_required
def export_members():
    require_admin()
    users = User.query.join(MemberProfile, isouter=True).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Member ID', 'Name', 'Email', 'Role', 'Department',
                     'Designation', 'Branch', 'Academic Year', 'USN',
                     'Contribution Points', 'Status', 'Joined'])
    for u in users:
        p = u.profile
        writer.writerow([
            u.member_id, p.full_name if p else '', u.email, u.role,
            p.department if p else '', p.designation if p else '',
            p.branch if p else '', p.academic_year if p else '',
            p.usn if p else '', p.contribution_points if p else 0,
            'Active' if u.is_active else 'Inactive',
            p.joined_date.strftime('%Y-%m-%d') if p and p.joined_date else ''
        ])

    output.seek(0)
    log_action('export_members', 'system')
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=members.csv'})


@admin_bp.route('/audit-logs')
@login_required
def audit_logs():
    require_admin()
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template('admin/audit_logs.html', logs=logs)


@admin_bp.route('/invitations')
@login_required
def invitations():
    require_admin()
    invites = Invitation.query.order_by(Invitation.created_at.desc()).all()
    return render_template('admin/invitations.html', invites=invites)


@admin_bp.route('/change-requests')
@login_required
def change_requests():
    require_admin()
    from app.models import ChangeRequest
    pending = ChangeRequest.query.filter_by(status='pending').order_by(ChangeRequest.created_at.desc()).all()
    reviewed = ChangeRequest.query.filter(ChangeRequest.status != 'pending').order_by(ChangeRequest.reviewed_at.desc()).limit(50).all()
    return render_template('admin/change_requests.html', pending=pending, reviewed=reviewed)


@admin_bp.route('/change-requests/<int:cr_id>/review', methods=['GET', 'POST'])
@login_required
def review_change_request(cr_id):
    require_admin()
    from app.models import ChangeRequest, MemberProfile
    import json as _json
    cr = ChangeRequest.query.get_or_404(cr_id)

    if request.method == 'POST':
        decision = request.form.get('decision')   # 'approved' or 'rejected'
        admin_notes = request.form.get('admin_notes', '').strip()
        cr.status = decision
        cr.admin_notes = admin_notes
        cr.reviewed_by = current_user.id
        cr.reviewed_at = datetime.utcnow()

        if decision == 'approved' and cr.target_type == 'profile' and cr.target_id:
            profile = MemberProfile.query.get(cr.target_id)
            if profile:
                changes = _json.loads(cr.field_changes or '{}')
                for field, vals in changes.items():
                    setattr(profile, field, vals.get('new', ''))
                profile.updated_at = datetime.utcnow()

        db.session.commit()
        log_action(f'change_request_{decision}', 'change_request', cr_id)

        create_notification(cr.user_id,
            f'Change Request {decision.title()}',
            f'Your {cr.target_type} change request was {decision}.' +
            (f' Admin note: {admin_notes}' if admin_notes else ''),
            'announcement', url_for('portal.profile'))

        flash(f'Change request {decision}.', 'success')
        return redirect(url_for('admin.change_requests'))

    # Parse field changes for display
    try:
        changes = _json.loads(cr.field_changes or '{}')
    except Exception:
        changes = {}
    return render_template('admin/review_change_request.html', cr=cr, changes=changes)


@admin_bp.route('/applications')
@login_required
def applications():
    require_admin()
    from app.models import MemberApplication
    pending  = MemberApplication.query.filter_by(status='pending').order_by(MemberApplication.submitted_at.desc()).all()
    reviewed = MemberApplication.query.filter(MemberApplication.status != 'pending').order_by(MemberApplication.reviewed_at.desc()).limit(50).all()
    return render_template('admin/applications.html', pending=pending, reviewed=reviewed)


@admin_bp.route('/applications/<int:app_id>/approve', methods=['POST'])
@login_required
def approve_application(app_id):
    require_admin()
    from app.models import MemberApplication
    app_obj = MemberApplication.query.get_or_404(app_id)

    if app_obj.status != 'pending':
        flash('This application has already been reviewed.', 'warning')
        return redirect(url_for('admin.applications'))

    app_obj.status      = 'approved'
    app_obj.admin_notes = request.form.get('admin_notes', '').strip()
    app_obj.reviewed_by = current_user.id
    app_obj.reviewed_at = datetime.utcnow()

    token = app_obj.generate_set_password_token()
    db.session.commit()

    set_pw_url = url_for('auth.set_password', token=token, _external=True)
    log_action('approve_application', 'application', app_id, app_obj.email)
    flash(f'Application approved! Share this activation link with {app_obj.full_name}: {set_pw_url}', 'success')
    return redirect(url_for('admin.applications'))


@admin_bp.route('/applications/<int:app_id>/reject', methods=['POST'])
@login_required
def reject_application(app_id):
    require_admin()
    from app.models import MemberApplication
    app_obj = MemberApplication.query.get_or_404(app_id)

    app_obj.status      = 'rejected'
    app_obj.admin_notes = request.form.get('admin_notes', '').strip()
    app_obj.reviewed_by = current_user.id
    app_obj.reviewed_at = datetime.utcnow()
    db.session.commit()

    log_action('reject_application', 'application', app_id, app_obj.email)
    flash(f'Application from {app_obj.full_name} rejected.', 'info')
    return redirect(url_for('admin.applications'))


@admin_bp.route('/members/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_member(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.members'))
    if user.is_admin():
        flash('Admin accounts cannot be deleted here. Use Super Admin controls.', 'danger')
        return redirect(url_for('admin.members'))

    name = user.profile.full_name if user.profile else user.email
    from app.models import Notification, AuditLog, ChangeRequest, Achievement
    Notification.query.filter_by(user_id=user.id).delete()
    AuditLog.query.filter_by(user_id=user.id).delete()
    ChangeRequest.query.filter_by(user_id=user.id).delete()
    Achievement.query.filter_by(user_id=user.id).delete()
    if user.profile:
        db.session.delete(user.profile)
    db.session.delete(user)
    db.session.commit()
    log_action('delete_member', 'user', user_id, name)
    flash(f'Member "{name}" has been permanently removed.', 'success')
    return redirect(url_for('admin.members'))
