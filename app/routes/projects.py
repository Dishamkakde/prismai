from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Project, Task, Milestone, User, MemberProfile, ProjectStatus, TaskStatus
from app.utils import admin_required, lead_required, log_action, generate_project_id, create_notification
from datetime import datetime, timezone, date

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/')
@login_required
def my_projects():
    projects = current_user.projects
    led_projects = Project.query.filter_by(lead_id=current_user.id).all()
    # Merge and deduplicate
    all_ids = {p.id for p in projects}
    for p in led_projects:
        if p.id not in all_ids:
            projects = list(projects) + [p]
    return render_template('portal/projects/list.html', projects=projects)


@projects_bp.route('/<int:project_id>')
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    # Access control
    is_member = current_user in project.members
    is_lead = project.lead_id == current_user.id
    is_admin = current_user.is_admin()
    if not (is_member or is_lead or is_admin):
        abort(403)

    tasks = project.tasks.all()
    milestones = project.milestones.order_by(Milestone.due_date).all()
    meetings = project.meetings.order_by('meeting_date').all()
    documents = project.documents.all()
    reports = project.progress_reports.order_by('week_start').all()
    research = project.research_papers

    task_stats = {
        'todo': len([t for t in tasks if t.status == TaskStatus.TODO]),
        'in_progress': len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS]),
        'review': len([t for t in tasks if t.status == TaskStatus.REVIEW]),
        'completed': len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
    }

    return render_template('portal/projects/detail.html',
                           project=project, tasks=tasks,
                           milestones=milestones, meetings=meetings,
                           documents=documents, reports=reports,
                           research=research, task_stats=task_stats,
                           is_lead=is_lead, is_admin=is_admin)


@projects_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_project():
    if not current_user.is_admin():
        abort(403)

    all_members = User.query.join(MemberProfile).filter(User.is_active == True).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Project title is required.', 'danger')
            return render_template('portal/projects/create.html', members=all_members)

        start_str = request.form.get('start_date')
        end_str = request.form.get('expected_end_date')
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else None
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else None

        project = Project(
            project_id=generate_project_id(),
            title=title,
            category=request.form.get('category', '').strip(),
            description=request.form.get('description', '').strip(),
            problem_statement=request.form.get('problem_statement', '').strip(),
            proposed_solution=request.form.get('proposed_solution', '').strip(),
            objectives=request.form.get('objectives', '').strip(),
            technologies=request.form.get('technologies', '').strip(),
            department=request.form.get('department', '').strip(),
            status=request.form.get('status', ProjectStatus.PLANNING),
            visibility=request.form.get('visibility', 'private'),
            start_date=start_date,
            expected_end_date=end_date,
            github_url=request.form.get('github_url', '').strip(),
            demo_url=request.form.get('demo_url', '').strip(),
            created_by=current_user.id
        )

        lead_id = request.form.get('lead_id')
        if lead_id:
            project.lead_id = int(lead_id)

        db.session.add(project)
        db.session.flush()

        member_ids = request.form.getlist('member_ids')
        for mid in member_ids:
            u = User.query.get(int(mid))
            if u and u not in project.members:
                project.members.append(u)
                create_notification(u.id, 'Added to Project',
                                    f'You have been added to project: {project.title}',
                                    'project', url_for('projects.project_detail', project_id=project.id))

        if lead_id:
            lead = User.query.get(int(lead_id))
            if lead and lead not in project.members:
                project.members.append(lead)

        db.session.commit()
        log_action('create_project', 'project', project.id, f'Created: {project.title}')
        flash(f'Project "{project.title}" created successfully.', 'success')
        return redirect(url_for('projects.project_detail', project_id=project.id))

    return render_template('portal/projects/create.html', members=all_members)


@projects_bp.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if not (current_user.is_admin() or project.lead_id == current_user.id):
        abort(403)

    all_members = User.query.join(MemberProfile).filter(User.is_active == True).all()

    if request.method == 'POST':
        project.title = request.form.get('title', project.title).strip()
        project.category = request.form.get('category', '').strip()
        project.description = request.form.get('description', '').strip()
        project.problem_statement = request.form.get('problem_statement', '').strip()
        project.proposed_solution = request.form.get('proposed_solution', '').strip()
        project.objectives = request.form.get('objectives', '').strip()
        project.technologies = request.form.get('technologies', '').strip()
        project.status = request.form.get('status', project.status)
        project.visibility = request.form.get('visibility', project.visibility)
        project.github_url = request.form.get('github_url', '').strip()
        project.demo_url = request.form.get('demo_url', '').strip()
        project.progress_percent = int(request.form.get('progress_percent', project.progress_percent) or 0)

        start_str = request.form.get('start_date')
        end_str = request.form.get('expected_end_date')
        if start_str:
            project.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        if end_str:
            project.expected_end_date = datetime.strptime(end_str, '%Y-%m-%d').date()

        if current_user.is_admin():
            lead_id = request.form.get('lead_id')
            if lead_id:
                project.lead_id = int(lead_id)
            member_ids = request.form.getlist('member_ids')
            project.members = []
            for mid in member_ids:
                u = User.query.get(int(mid))
                if u:
                    project.members.append(u)

        db.session.commit()
        log_action('edit_project', 'project', project.id)
        flash('Project updated successfully.', 'success')
        return redirect(url_for('projects.project_detail', project_id=project.id))

    return render_template('portal/projects/edit.html', project=project, members=all_members)


@projects_bp.route('/<int:project_id>/milestones/add', methods=['POST'])
@login_required
def add_milestone(project_id):
    project = Project.query.get_or_404(project_id)
    if not (current_user.is_admin() or project.lead_id == current_user.id):
        abort(403)

    title = request.form.get('title', '').strip()
    if title:
        due_str = request.form.get('due_date')
        due_date = datetime.strptime(due_str, '%Y-%m-%d').date() if due_str else None
        m = Milestone(project_id=project_id, title=title,
                      description=request.form.get('description', '').strip(),
                      due_date=due_date)
        db.session.add(m)
        db.session.commit()
        flash('Milestone added.', 'success')
    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/milestones/<int:milestone_id>/complete', methods=['POST'])
@login_required
def complete_milestone(milestone_id):
    m = Milestone.query.get_or_404(milestone_id)
    project = Project.query.get(m.project_id)
    if not (current_user.is_admin() or project.lead_id == current_user.id):
        abort(403)
    m.is_completed = True
    m.completed_at = datetime.utcnow()
    db.session.commit()
    flash('Milestone marked as completed.', 'success')
    return redirect(url_for('projects.project_detail', project_id=m.project_id))
