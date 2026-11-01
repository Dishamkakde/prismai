from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, current_app, send_from_directory)
from flask_login import login_required, current_user
from app import db
from app.models import GalleryAlbum, GalleryPhoto
from app.utils import log_action, admin_required
from datetime import datetime
import os, uuid

gallery_bp = Blueprint('gallery', __name__)

ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def _save_photo(file, subfolder='gallery'):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED:
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(folder, exist_ok=True)
    file.save(os.path.join(folder, filename))
    return f"{subfolder}/{filename}"


# ── PUBLIC GALLERY ─────────────────────────────
@gallery_bp.route('/')
def public_gallery():
    """Public gallery — shows all published albums."""
    albums = GalleryAlbum.query.filter_by(is_published=True)\
                .order_by(GalleryAlbum.event_date.desc()).all()
    return render_template('gallery/public.html', albums=albums)


@gallery_bp.route('/album/<int:album_id>')
def view_album(album_id):
    """Public view of a single published album."""
    album = GalleryAlbum.query.get_or_404(album_id)
    if not album.is_published and not (current_user.is_authenticated and current_user.is_admin()):
        abort(404)
    photos = album.photos.order_by(GalleryPhoto.position).all()
    return render_template('gallery/album.html', album=album, photos=photos)


# ── ADMIN GALLERY MANAGEMENT ───────────────────
@gallery_bp.route('/admin')
@login_required
def admin_gallery():
    """Admin view — all albums (published + drafts)."""
    if not current_user.is_admin():
        abort(403)
    albums = GalleryAlbum.query.order_by(GalleryAlbum.created_at.desc()).all()
    return render_template('gallery/admin_list.html', albums=albums)


@gallery_bp.route('/admin/create', methods=['GET', 'POST'])
@login_required
def create_album():
    if not current_user.is_admin():
        abort(403)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Album title is required.', 'danger')
            return render_template('gallery/create_album.html')

        event_date_str = request.form.get('event_date')
        event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date() if event_date_str else None

        album = GalleryAlbum(
            title=title,
            description=request.form.get('description', '').strip(),
            category=request.form.get('category', 'General').strip(),
            event_date=event_date,
            is_published=request.form.get('is_published') == 'on',
            created_by=current_user.id
        )
        db.session.add(album)
        db.session.flush()

        # Upload photos
        files = request.files.getlist('photos')
        position = 0
        cover_set = False
        for file in files:
            if file and file.filename:
                path = _save_photo(file)
                if path:
                    photo = GalleryPhoto(
                        album_id=album.id,
                        file_path=path,
                        caption=request.form.get('caption', '').strip(),
                        credit=request.form.get('credit', '').strip(),
                        position=position,
                        uploaded_by=current_user.id
                    )
                    db.session.add(photo)
                    if not cover_set:
                        album.cover_image = path
                        cover_set = True
                    position += 1

        db.session.commit()
        log_action('create_gallery_album', 'gallery', album.id, title)
        flash(f'Album "{title}" created with {position} photo(s).', 'success')
        return redirect(url_for('gallery.manage_album', album_id=album.id))

    categories = ['Events', 'Workshop', 'Hackathon', 'Competition',
                  'Team Activities', 'Guest Lecture', 'Behind the Scenes', 'General']
    return render_template('gallery/create_album.html', categories=categories)


@gallery_bp.route('/admin/album/<int:album_id>', methods=['GET', 'POST'])
@login_required
def manage_album(album_id):
    if not current_user.is_admin():
        abort(403)
    album = GalleryAlbum.query.get_or_404(album_id)
    photos = album.photos.order_by(GalleryPhoto.position).all()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'edit_album':
            album.title = request.form.get('title', album.title).strip()
            album.description = request.form.get('description', '').strip()
            album.category = request.form.get('category', album.category)
            event_date_str = request.form.get('event_date')
            if event_date_str:
                album.event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            album.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Album details updated.', 'success')

        elif action == 'add_photos':
            files = request.files.getlist('photos')
            added = 0
            pos = album.photos.count()
            for file in files:
                if file and file.filename:
                    path = _save_photo(file)
                    if path:
                        photo = GalleryPhoto(
                            album_id=album.id,
                            file_path=path,
                            caption=request.form.get('caption', '').strip(),
                            credit=request.form.get('credit', '').strip(),
                            position=pos,
                            uploaded_by=current_user.id
                        )
                        db.session.add(photo)
                        if not album.cover_image:
                            album.cover_image = path
                        pos += 1
                        added += 1
            db.session.commit()
            flash(f'{added} photo(s) added.', 'success')

        elif action == 'set_cover':
            photo_id = request.form.get('photo_id')
            photo = GalleryPhoto.query.get(int(photo_id))
            if photo and photo.album_id == album.id:
                album.cover_image = photo.file_path
                db.session.commit()
                flash('Cover photo updated.', 'success')

        elif action == 'delete_photo':
            photo_id = request.form.get('photo_id')
            photo = GalleryPhoto.query.get(int(photo_id))
            if photo and photo.album_id == album.id:
                db.session.delete(photo)
                if album.cover_image == photo.file_path:
                    album.cover_image = None
                db.session.commit()
                flash('Photo deleted.', 'success')

        elif action == 'update_caption':
            photo_id = request.form.get('photo_id')
            photo = GalleryPhoto.query.get(int(photo_id))
            if photo and photo.album_id == album.id:
                photo.caption = request.form.get('caption', '').strip()
                photo.credit  = request.form.get('credit', '').strip()
                db.session.commit()
                flash('Caption updated.', 'success')

        elif action == 'toggle_publish':
            album.is_published = not album.is_published
            db.session.commit()
            state = 'published' if album.is_published else 'unpublished'
            flash(f'Album {state}.', 'success')
            log_action(f'gallery_album_{state}', 'gallery', album.id)

        elif action == 'delete_album':
            title = album.title
            db.session.delete(album)
            db.session.commit()
            log_action('delete_gallery_album', 'gallery', album_id, title)
            flash(f'Album "{title}" deleted.', 'success')
            return redirect(url_for('gallery.admin_gallery'))

        return redirect(url_for('gallery.manage_album', album_id=album_id))

    categories = ['Events', 'Workshop', 'Hackathon', 'Competition',
                  'Team Activities', 'Guest Lecture', 'Behind the Scenes', 'General']
    return render_template('gallery/manage_album.html',
                           album=album, photos=photos, categories=categories)
