from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Task, TaskSubmission, TaskComment, Project, User, TaskStatus, TaskPriority
from app.utils import log_action, create_notification, save_file
from datetime import datetime, timezone

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/')
@login_required
def my_tasks():
    tasks = Task.query.filter_by(assignee_id=current_user.id).order_by(Task.due_date).all()
    todo = [t for t in tasks if t.status == TaskStatus.TODO]
    in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
    review = [t for t in tasks if t.status == TaskStatus.REVIEW]
    completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    return render_template('portal/tasks/list.html',
                           todo=todo, in_progress=in_progress,
                           review=review, completed=completed)


@tasks_bp.route('/<int:task_id>')
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    project = task.project
    is_assignee = task.assignee_id == current_user.id
    is_lead = project.lead_id == current_user.id
    is_admin = current_user.is_admin()
    if not (is_assignee or is_lead or is_admin):
        abort(403)
    comments = task.comments.order_by('created_at').all()
    submissions = task.submissions.order_by('submitted_at').all()
    return render_template('portal/tasks/detail.html', task=task,
                           comments=comments, submissions=submissions,
                           is_assignee=is_assignee, is_lead=is_lead, is_admin=is_admin)


@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if not current_user.is_project_lead():
        abort(403)

    # Get projects where user is lead or admin
    if current_user.is_admin():
        my_projects = Project.query.all()
    else:
        my_projects = Project.query.filter_by(lead_id=current_user.id).all()

    if request.method == 'POST':
        project_id = request.form.get('project_id')
        if not project_id:
            flash('Project is required.', 'danger')
            return render_template('portal/tasks/create.html', projects=my_projects)

        project = Project.query.get_or_404(int(project_id))
        if not (current_user.is_admin() or project.lead_id == current_user.id):
            abort(403)

        title = request.form.get('title', '').strip()
        if not title:
            flash('Task title is required.', 'danger')
            return render_template('portal/tasks/create.html', projects=my_projects)

        due_str = request.form.get('due_date')
        due_date = datetime.strptime(due_str, '%Y-%m-%d').date() if due_str else None

        task = Task(
            project_id=project.id,
            title=title,
            description=request.form.get('description', '').strip(),
            priority=request.form.get('priority', TaskPriority.MEDIUM),
            status=TaskStatus.TODO,
            reference_materials=request.form.get('reference_materials', '').strip(),
            due_date=due_date,
            created_by=current_user.id
        )
        assignee_id = request.form.get('assignee_id')
        if assignee_id:
            task.assignee_id = int(assignee_id)

        db.session.add(task)
        db.session.commit()

        if task.assignee_id:
            create_notification(task.assignee_id, 'New Task Assigned',
                                f'You have been assigned: {task.title}',
                                'task', url_for('tasks.task_detail', task_id=task.id))

        log_action('create_task', 'task', task.id, title)
        flash('Task created successfully.', 'success')
        return redirect(url_for('tasks.task_detail', task_id=task.id))

    return render_template('portal/tasks/create.html', projects=my_projects)


@tasks_bp.route('/<int:task_id>/update-status', methods=['POST'])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    if not (task.assignee_id == current_user.id or current_user.is_project_lead()):
        abort(403)

    new_status = request.form.get('status')
    valid_statuses = [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.COMPLETED]
    if new_status not in valid_statuses:
        flash('Invalid status.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    # Members can only move to In Progress or Review, not directly to Completed
    if not current_user.is_project_lead() and new_status == TaskStatus.COMPLETED:
        flash('Only project leads can mark tasks as completed.', 'warning')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    task.status = new_status
    if new_status == TaskStatus.COMPLETED:
        task.completed_at = datetime.utcnow()
    db.session.commit()
    log_action('update_task_status', 'task', task_id, new_status)
    flash('Task status updated.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


@tasks_bp.route('/<int:task_id>/submit', methods=['POST'])
@login_required
def submit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.assignee_id != current_user.id:
        abort(403)

    file_path = None
    if 'submission_file' in request.files:
        file = request.files['submission_file']
        if file and file.filename:
            file_path = save_file(file, 'submissions')

    submission = TaskSubmission(
        task_id=task_id,
        submitted_by=current_user.id,
        submission_notes=request.form.get('notes', '').strip(),
        submission_link=request.form.get('submission_link', '').strip(),
        file_path=file_path
    )
    db.session.add(submission)
    task.status = TaskStatus.REVIEW
    db.session.commit()

    # Notify project lead
    project = task.project
    if project.lead_id:
        create_notification(project.lead_id, 'Task Submitted for Review',
                            f'{current_user.profile.full_name} submitted: {task.title}',
                            'task', url_for('tasks.task_detail', task_id=task_id))

    flash('Work submitted for review.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


@tasks_bp.route('/submissions/<int:submission_id>/review', methods=['POST'])
@login_required
def review_submission(submission_id):
    submission = TaskSubmission.query.get_or_404(submission_id)
    task = submission.task
    project = task.project
    if not (current_user.is_admin() or project.lead_id == current_user.id):
        abort(403)

    decision = request.form.get('decision')
    notes = request.form.get('reviewer_notes', '').strip()
    submission.status = decision
    submission.reviewer_notes = notes
    submission.reviewed_by = current_user.id
    submission.reviewed_at = datetime.utcnow()

    if decision == 'Approved':
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        create_notification(submission.submitted_by, 'Task Approved',
                            f'Your submission for "{task.title}" was approved!',
                            'task', url_for('tasks.task_detail', task_id=task.id))
    elif decision == 'Rejected':
        task.status = TaskStatus.IN_PROGRESS
        create_notification(submission.submitted_by, 'Task Needs Revision',
                            f'Your submission for "{task.title}" needs revision.',
                            'task', url_for('tasks.task_detail', task_id=task.id))

    db.session.commit()
    flash(f'Submission {decision}.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task.id))


@tasks_bp.route('/<int:task_id>/comment', methods=['POST'])
@login_required
def add_comment(task_id):
    task = Task.query.get_or_404(task_id)
    project = task.project
    is_member = current_user in project.members
    is_lead = project.lead_id == current_user.id
    if not (is_member or is_lead or current_user.is_admin()):
        abort(403)

    content = request.form.get('content', '').strip()
    if content:
        from app.models import TaskComment
        comment = TaskComment(task_id=task_id, user_id=current_user.id, content=content)
        db.session.add(comment)
        db.session.commit()
        flash('Comment added.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))
