from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import WeeklyReport, Project
from app.utils import log_action, create_notification
from datetime import datetime, timezone, date, timedelta

reports_bp = Blueprint('reports', __name__)


def get_week_range():
    today = date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=6)  # Sunday
    return start, end


@reports_bp.route('/')
@login_required
def my_reports():
    reports = WeeklyReport.query.filter_by(user_id=current_user.id).order_by(
        WeeklyReport.week_start.desc()).all()
    return render_template('portal/reports/list.html', reports=reports)


@reports_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_report():
    if current_user.is_admin():
        my_projects = Project.query.all()
    else:
        my_projects = current_user.projects

    if not my_projects:
        flash('You are not assigned to any projects yet.', 'warning')
        return redirect(url_for('reports.my_reports'))

    week_start, week_end = get_week_range()

    if request.method == 'POST':
        project_id = request.form.get('project_id')
        if not project_id:
            flash('Project is required.', 'danger')
            return render_template('portal/reports/submit.html', projects=my_projects,
                                   week_start=week_start, week_end=week_end)

        # Check for duplicate
        existing = WeeklyReport.query.filter_by(
            user_id=current_user.id,
            project_id=int(project_id),
            week_start=week_start
        ).first()
        if existing:
            flash('You have already submitted a report for this week.', 'warning')
            return redirect(url_for('reports.my_reports'))

        report = WeeklyReport(
            user_id=current_user.id,
            project_id=int(project_id),
            week_start=week_start,
            week_end=week_end,
            work_completed=request.form.get('work_completed', '').strip(),
            tasks_completed=request.form.get('tasks_completed', '').strip(),
            current_work=request.form.get('current_work', '').strip(),
            challenges=request.form.get('challenges', '').strip(),
            research_progress=request.form.get('research_progress', '').strip(),
            next_week_goals=request.form.get('next_week_goals', '').strip(),
            assistance_required=request.form.get('assistance_required', '').strip(),
            supporting_links=request.form.get('supporting_links', '').strip()
        )
        db.session.add(report)
        db.session.commit()

        # Notify project lead
        project = Project.query.get(int(project_id))
        if project and project.lead_id:
            create_notification(project.lead_id, 'Weekly Report Submitted',
                                f'{current_user.profile.full_name} submitted their weekly report.',
                                'report', url_for('reports.review_report', report_id=report.id))

        log_action('submit_report', 'report', report.id)
        flash('Weekly report submitted successfully.', 'success')
        return redirect(url_for('reports.my_reports'))

    return render_template('portal/reports/submit.html', projects=my_projects,
                           week_start=week_start, week_end=week_end)


@reports_bp.route('/<int:report_id>')
@login_required
def view_report(report_id):
    report = WeeklyReport.query.get_or_404(report_id)
    if not (report.user_id == current_user.id or current_user.is_admin() or
            (report.project and report.project.lead_id == current_user.id)):
        abort(403)
    return render_template('portal/reports/view.html', report=report)


@reports_bp.route('/<int:report_id>/review', methods=['GET', 'POST'])
@login_required
def review_report(report_id):
    report = WeeklyReport.query.get_or_404(report_id)
    project = report.project
    if not (current_user.is_admin() or
            (project and project.lead_id == current_user.id)):
        abort(403)

    if request.method == 'POST':
        report.feedback = request.form.get('feedback', '').strip()
        report.status = 'Reviewed'
        report.reviewed_by = current_user.id
        report.reviewed_at = datetime.utcnow()
        db.session.commit()
        create_notification(report.user_id, 'Report Feedback',
                            'Your weekly report has received feedback.',
                            'report', url_for('reports.view_report', report_id=report_id))
        flash('Feedback submitted.', 'success')
        return redirect(url_for('reports.view_report', report_id=report_id))

    return render_template('portal/reports/review.html', report=report)


@reports_bp.route('/team')
@login_required
def team_reports():
    if not current_user.is_project_lead():
        abort(403)

    if current_user.is_admin():
        reports = WeeklyReport.query.order_by(WeeklyReport.submitted_at.desc()).all()
    else:
        lead_project_ids = [p.id for p in Project.query.filter_by(lead_id=current_user.id).all()]
        reports = WeeklyReport.query.filter(
            WeeklyReport.project_id.in_(lead_project_ids)
        ).order_by(WeeklyReport.submitted_at.desc()).all()

    return render_template('portal/reports/team.html', reports=reports)
