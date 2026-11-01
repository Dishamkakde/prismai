from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_from_directory, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Document, Project
from app.utils import log_action, save_file
import os

documents_bp = Blueprint('documents', __name__)

CATEGORIES = ['Research Paper', 'Project Report', 'Presentation', 'Dataset',
              'Documentation', 'Meeting Minutes', 'Reference', 'Tutorial', 'Other']


@documents_bp.route('/')
@login_required
def library():
    category = request.args.get('category', '')
    project_filter = request.args.get('project_id', '')

    if current_user.is_admin():
        query = Document.query
    else:
        project_ids = [p.id for p in current_user.projects]
        query = Document.query.filter(
            (Document.access_level == 'public') |
            (Document.uploaded_by == current_user.id) |
            (Document.project_id.in_(project_ids) & (Document.access_level.in_(['project', 'public'])))
        )

    if category:
        query = query.filter_by(category=category)
    if project_filter:
        query = query.filter_by(project_id=int(project_filter))

    documents = query.order_by(Document.created_at.desc()).all()
    my_projects = current_user.projects if not current_user.is_admin() else Project.query.all()

    return render_template('portal/documents/library.html',
                           documents=documents, categories=CATEGORIES,
                           projects=my_projects, selected_category=category)


@documents_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_document():
    if current_user.is_admin():
        my_projects = Project.query.all()
    else:
        if not current_user.is_project_lead():
            abort(403)
        my_projects = Project.query.filter_by(lead_id=current_user.id).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Document title is required.', 'danger')
            return render_template('portal/documents/upload.html', projects=my_projects, categories=CATEGORIES)

        if 'document_file' not in request.files or not request.files['document_file'].filename:
            flash('Please select a file to upload.', 'danger')
            return render_template('portal/documents/upload.html', projects=my_projects, categories=CATEGORIES)

        file = request.files['document_file']
        file_path = save_file(file, 'documents')
        if not file_path:
            flash('Invalid file type.', 'danger')
            return render_template('portal/documents/upload.html', projects=my_projects, categories=CATEGORIES)

        project_id = request.form.get('project_id') or None

        doc = Document(
            title=title,
            description=request.form.get('description', '').strip(),
            file_path=file_path,
            file_type=file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'unknown',
            category=request.form.get('category', 'Other'),
            access_level=request.form.get('access_level', 'project'),
            project_id=int(project_id) if project_id else None,
            uploaded_by=current_user.id
        )
        db.session.add(doc)
        db.session.commit()
        log_action('upload_document', 'document', doc.id, title)
        flash('Document uploaded successfully.', 'success')
        return redirect(url_for('documents.library'))

    return render_template('portal/documents/upload.html', projects=my_projects, categories=CATEGORIES)


@documents_bp.route('/download/<int:doc_id>')
@login_required
def download_document(doc_id):
    doc = Document.query.get_or_404(doc_id)

    # Access check
    project_ids = [p.id for p in current_user.projects]
    if doc.access_level == 'admin' and not current_user.is_admin():
        abort(403)
    if doc.access_level == 'project':
        if not (current_user.is_admin() or doc.uploaded_by == current_user.id or
                (doc.project_id and doc.project_id in project_ids)):
            abort(403)

    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_dir = os.path.join(upload_folder, os.path.dirname(doc.file_path))
    file_name = os.path.basename(doc.file_path)
    log_action('download_document', 'document', doc_id)
    return send_from_directory(file_dir, file_name, as_attachment=True)
