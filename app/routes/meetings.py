from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Meeting, Project, User
from app.utils import log_action, create_notification
from datetime import datetime, timezone

meetings_bp = Blueprint('meetings', __name__)


@meetings_bp.route('/')
@login_required
def my_meetings():
    if current_user.is_admin():
        meetings = Meeting.query.order_by(Meeting.meeting_date).all()
    else:
        meetings = Meeting.query.filter(
            Meeting.participants.any(id=current_user.id)
        ).order_by(Meeting.meeting_date).all()

    now = datetime.utcnow()
    upcoming = [m for m in meetings if m.meeting_date >= now]
    past = [m for m in meetings if m.meeting_date < now]
    return render_template('portal/meetings/list.html', upcoming=upcoming, past=past)


@meetings_bp.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule_meeting():
    if not current_user.is_project_lead():
        abort(403)

    if current_user.is_admin():
        my_projects = Project.query.all()
        all_members = User.query.filter_by(is_active=True).all()
    else:
        my_projects = Project.query.filter_by(lead_id=current_user.id).all()
        member_ids = set()
        for p in my_projects:
            for m in p.members:
                member_ids.add(m.id)
        all_members = User.query.filter(User.id.in_(member_ids)).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        date_str = request.form.get('meeting_date')
        time_str = request.form.get('meeting_time')

        if not title or not date_str or not time_str:
            flash('Title, date, and time are required.', 'danger')
            return render_template('portal/meetings/schedule.html',
                                   projects=my_projects, members=all_members)

        dt_str = f"{date_str} {time_str}"
        meeting_dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')

        project_id = request.form.get('project_id') or None

        meeting = Meeting(
            title=title,
            description=request.form.get('description', '').strip(),
            meeting_date=meeting_dt,
            duration_minutes=int(request.form.get('duration_minutes', 60) or 60),
            venue=request.form.get('venue', '').strip(),
            meeting_link=request.form.get('meeting_link', '').strip(),
            meeting_type=request.form.get('meeting_type', 'team'),
            agenda=request.form.get('agenda', '').strip(),
            project_id=int(project_id) if project_id else None,
            organized_by=current_user.id
        )
        db.session.add(meeting)
        db.session.flush()

        participant_ids = request.form.getlist('participant_ids')
        for pid in participant_ids:
            u = User.query.get(int(pid))
            if u:
                meeting.participants.append(u)
                if u.id != current_user.id:
                    create_notification(u.id, 'Meeting Scheduled',
                                        f'New meeting: {meeting.title} on {meeting_dt.strftime("%b %d at %H:%M")}',
                                        'meeting', url_for('meetings.meeting_detail', meeting_id=meeting.id))

        if current_user not in meeting.participants:
            meeting.participants.append(current_user)

        db.session.commit()
        log_action('schedule_meeting', 'meeting', meeting.id)
        flash('Meeting scheduled successfully.', 'success')
        return redirect(url_for('meetings.meeting_detail', meeting_id=meeting.id))

    return render_template('portal/meetings/schedule.html', projects=my_projects, members=all_members)


@meetings_bp.route('/<int:meeting_id>')
@login_required
def meeting_detail(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    is_participant = current_user in meeting.participants
    is_organizer = meeting.organized_by == current_user.id
    if not (is_participant or is_organizer or current_user.is_admin()):
        abort(403)
    return render_template('portal/meetings/detail.html', meeting=meeting,
                           is_organizer=is_organizer)


@meetings_bp.route('/<int:meeting_id>/update', methods=['POST'])
@login_required
def update_meeting(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    if not (meeting.organized_by == current_user.id or current_user.is_admin()):
        abort(403)

    meeting.minutes = request.form.get('minutes', '').strip()
    meeting.decisions = request.form.get('decisions', '').strip()
    meeting.follow_up_tasks = request.form.get('follow_up_tasks', '').strip()
    db.session.commit()
    flash('Meeting notes updated.', 'success')
    return redirect(url_for('meetings.meeting_detail', meeting_id=meeting_id))
