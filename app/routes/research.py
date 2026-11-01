from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_from_directory
from flask_login import login_required, current_user
from app import db
from app.models import ResearchPaper, Project, User
from app.utils import log_action, save_file
from datetime import datetime

research_bp = Blueprint('research', __name__)


@research_bp.route('/')
@login_required
def hub():
    if current_user.is_admin():
        papers = ResearchPaper.query.order_by(ResearchPaper.created_at.desc()).all()
    else:
        project_ids = [p.id for p in current_user.projects]
        papers = ResearchPaper.query.filter(
            (ResearchPaper.uploaded_by == current_user.id) |
            (ResearchPaper.project_id.in_(project_ids))
        ).order_by(ResearchPaper.created_at.desc()).all()

    topics = db.session.query(ResearchPaper.research_topic).distinct().all()
    topics = [t[0] for t in topics if t[0]]
    return render_template('portal/research/hub.html', papers=papers, topics=topics)


@research_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_paper():
    if current_user.is_admin():
        my_projects = Project.query.all()
    else:
        my_projects = current_user.projects

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Paper title is required.', 'danger')
            return render_template('portal/research/add.html', projects=my_projects)

        pub_str = request.form.get('publication_date')
        pub_date = datetime.strptime(pub_str, '%Y-%m-%d').date() if pub_str else None

        file_path = None
        if 'paper_file' in request.files:
            f = request.files['paper_file']
            if f and f.filename:
                file_path = save_file(f, 'research')

        project_id = request.form.get('project_id') or None
        if project_id:
            project_id = int(project_id)

        paper = ResearchPaper(
            title=title,
            authors=request.form.get('authors', '').strip(),
            source=request.form.get('source', '').strip(),
            publication_date=pub_date,
            publication_link=request.form.get('publication_link', '').strip(),
            research_topic=request.form.get('research_topic', '').strip(),
            methodology=request.form.get('methodology', '').strip(),
            key_findings=request.form.get('key_findings', '').strip(),
            research_gaps=request.form.get('research_gaps', '').strip(),
            references=request.form.get('references', '').strip(),
            notes=request.form.get('notes', '').strip(),
            file_path=file_path,
            project_id=project_id,
            uploaded_by=current_user.id
        )

        assigned_id = request.form.get('assigned_researcher')
        if assigned_id:
            paper.assigned_researcher = int(assigned_id)

        db.session.add(paper)
        db.session.commit()
        log_action('add_research_paper', 'research', paper.id, title)
        flash('Research paper added successfully.', 'success')
        return redirect(url_for('research.hub'))

    all_members = User.query.filter_by(is_active=True).all() if current_user.is_admin() else []
    return render_template('portal/research/add.html', projects=my_projects, members=all_members)


@research_bp.route('/<int:paper_id>')
@login_required
def paper_detail(paper_id):
    paper = ResearchPaper.query.get_or_404(paper_id)
    project_ids = [p.id for p in current_user.projects]
    if not (current_user.is_admin() or paper.uploaded_by == current_user.id or
            (paper.project_id and paper.project_id in project_ids)):
        abort(403)
    return render_template('portal/research/detail.html', paper=paper)


@research_bp.route('/<int:paper_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_paper(paper_id):
    paper = ResearchPaper.query.get_or_404(paper_id)
    if not (current_user.is_admin() or paper.uploaded_by == current_user.id):
        abort(403)

    if request.method == 'POST':
        paper.title = request.form.get('title', paper.title).strip()
        paper.authors = request.form.get('authors', '').strip()
        paper.source = request.form.get('source', '').strip()
        paper.research_topic = request.form.get('research_topic', '').strip()
        paper.methodology = request.form.get('methodology', '').strip()
        paper.key_findings = request.form.get('key_findings', '').strip()
        paper.research_gaps = request.form.get('research_gaps', '').strip()
        paper.references = request.form.get('references', '').strip()
        paper.notes = request.form.get('notes', '').strip()
        paper.publication_link = request.form.get('publication_link', '').strip()
        db.session.commit()
        flash('Research paper updated.', 'success')
        return redirect(url_for('research.paper_detail', paper_id=paper_id))

    if current_user.is_admin():
        my_projects = Project.query.all()
    else:
        my_projects = current_user.projects
    return render_template('portal/research/edit.html', paper=paper, projects=my_projects)
