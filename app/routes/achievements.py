from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Achievement, MemberProfile, User
from app.utils import log_action, create_notification, save_file

achievements_bp = Blueprint('achievements', __name__)

CATEGORIES = ['Project Participation', 'Research Contribution', 'Paper Publication',
              'Hackathon', 'Competition', 'Open Source', 'Workshop',
              'Technical Presentation', 'Project Completion', 'Other']

POINT_VALUES = {
    'Project Participation': 10,
    'Research Contribution': 20,
    'Paper Publication': 50,
    'Hackathon': 30,
    'Competition': 25,
    'Open Source': 15,
    'Workshop': 10,
    'Technical Presentation': 20,
    'Project Completion': 40,
    'Other': 5
}


@achievements_bp.route('/')
@login_required
def my_achievements():
    achievements = Achievement.query.filter_by(
        user_id=current_user.id, is_verified=True
    ).order_by(Achievement.awarded_at.desc()).all()
    profile = current_user.profile
    return render_template('portal/achievements/list.html',
                           achievements=achievements, profile=profile)


@achievements_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_achievement():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'Other')
        description = request.form.get('description', '').strip()

        if not title:
            flash('Achievement title is required.', 'danger')
            return render_template('portal/achievements/submit.html', categories=CATEGORIES)

        cert_path = None
        if 'certificate' in request.files:
            f = request.files['certificate']
            if f and f.filename:
                cert_path = save_file(f, 'certificates')

        achievement = Achievement(
            user_id=current_user.id,
            title=title,
            description=description,
            category=category,
            points=POINT_VALUES.get(category, 5),
            certificate_path=cert_path,
            is_verified=False  # Needs admin approval
        )
        db.session.add(achievement)
        db.session.commit()

        # Notify admins
        admins = User.query.filter(User.role.in_(['admin', 'research_head'])).all()
        for admin in admins:
            create_notification(admin.id, 'Achievement Submitted for Verification',
                                f'{current_user.profile.full_name} submitted: {title}',
                                'achievement', url_for('achievements.verify_achievement', ach_id=achievement.id))

        flash('Achievement submitted for verification.', 'success')
        return redirect(url_for('achievements.my_achievements'))

    return render_template('portal/achievements/submit.html', categories=CATEGORIES)


@achievements_bp.route('/verify/<int:ach_id>', methods=['GET', 'POST'])
@login_required
def verify_achievement(ach_id):
    if not current_user.is_admin():
        abort(403)
    achievement = Achievement.query.get_or_404(ach_id)

    if request.method == 'POST':
        decision = request.form.get('decision')
        if decision == 'approve':
            achievement.is_verified = True
            achievement.awarded_by = current_user.id
            points = int(request.form.get('points', achievement.points) or achievement.points)
            achievement.points = points

            # Update contribution points
            profile = MemberProfile.query.filter_by(user_id=achievement.user_id).first()
            if profile:
                profile.contribution_points = (profile.contribution_points or 0) + points

            db.session.commit()
            create_notification(achievement.user_id, 'Achievement Verified',
                                f'Your achievement "{achievement.title}" has been verified! +{points} points',
                                'achievement', url_for('achievements.my_achievements'))
            log_action('verify_achievement', 'achievement', ach_id, 'approved')
            flash('Achievement approved and points awarded.', 'success')
        else:
            db.session.delete(achievement)
            db.session.commit()
            flash('Achievement rejected.', 'info')
        return redirect(url_for('admin.achievements'))

    return render_template('portal/achievements/verify.html', achievement=achievement,
                           categories=CATEGORIES, point_values=POINT_VALUES)


@achievements_bp.route('/leaderboard')
@login_required
def leaderboard():
    profiles = MemberProfile.query.filter(
        MemberProfile.contribution_points > 0
    ).order_by(MemberProfile.contribution_points.desc()).limit(20).all()
    return render_template('portal/achievements/leaderboard.html', profiles=profiles)
