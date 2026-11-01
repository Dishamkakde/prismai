from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, MemberProfile, Invitation, Role
from app.utils import generate_member_id, log_action, create_notification
from datetime import datetime, timedelta, date

auth_bp = Blueprint('auth', __name__)


def _now():
    """Return naive UTC datetime — matches what SQLite stores."""
    return datetime.utcnow()


def is_valid_password(password):
    return len(password) >= 8


def _is_expired(dt):
    """Check if a stored datetime (naive UTC) is in the past."""
    if dt is None:
        return False
    # dt from DB is naive; _now() is also naive — safe to compare
    return _now() > dt


# ── CHOICE PAGE ────────────────────────────────
@auth_bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard') if current_user.is_admin() else url_for('portal.dashboard'))
    return render_template('auth/choice.html')


# ── UNIFIED SIGN IN ─────────────────────────────
@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard') if current_user.is_admin() else url_for('portal.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not email or not password:
            flash('Please enter your Gmail and password.', 'danger')
            return render_template('auth/signin.html')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Contact the admin.', 'danger')
                return render_template('auth/signin.html')

            # Members must be approved before they can sign in
            if not user.is_admin() and not user.is_approved:
                flash('Your account is pending admin approval. You will be notified once approved.', 'warning')
                return render_template('auth/signin.html')

            login_user(user, remember=remember)
            user.last_login = _now()
            db.session.commit()
            log_action('login', 'user', user.id)

            return redirect(url_for('admin.dashboard') if user.is_admin() else url_for('portal.dashboard'))
        else:
            flash('Invalid Gmail or password.', 'danger')

    return render_template('auth/signin.html')


# ── LEGACY REDIRECTS (keep URLs working) ────────
@auth_bp.route('/login/member')
@auth_bp.route('/login/lead')
@auth_bp.route('/login/admin')
def login_redirect():
    return redirect(url_for('auth.signin'))


# ── SIGNUP (enter invitation code) ──────────────
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('portal.dashboard'))

    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        if not token:
            flash('Please enter your invitation code.', 'danger')
            return render_template('auth/signup.html')

        # Accept full URL or bare token
        if 'register/' in token:
            token = token.split('register/')[-1].split('?')[0].strip()

        invitation = Invitation.query.filter_by(token=token, is_used=False).first()
        if not invitation:
            flash('Invalid or already-used invitation code.', 'danger')
            return render_template('auth/signup.html')

        if _is_expired(invitation.expires_at):
            flash('This invitation has expired. Ask the admin to send a new one.', 'danger')
            return render_template('auth/signup.html')

        return redirect(url_for('auth.register', token=token))

    return render_template('auth/signup.html')


# ── REGISTER (fill in details after invitation) ─
@auth_bp.route('/register/<token>', methods=['GET', 'POST'])
def register(token):
    # Do NOT redirect authenticated users — they might be testing an invite link
    # or the invited person opened it while the admin was logged in on the same device.
    # Instead, show a notice in the template.
    already_logged_in = current_user.is_authenticated

    invitation = Invitation.query.filter_by(token=token, is_used=False).first()
    if not invitation:
        flash('Invalid or already-used invitation link.', 'danger')
        return redirect(url_for('auth.signup'))

    if _is_expired(invitation.expires_at):
        flash('This invitation has expired. Ask the admin to send a new one.', 'danger')
        return redirect(url_for('auth.signup'))

    if request.method == 'POST':
        full_name        = request.form.get('full_name', '').strip()
        password         = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        usn              = request.form.get('usn', '').strip()
        branch           = request.form.get('branch', '').strip()
        academic_year    = request.form.get('academic_year', '').strip()
        phone            = request.form.get('phone', '').strip()

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not is_valid_password(password):
            errors.append('Password must be at least 8 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/register.html', invitation=invitation,
                                   already_logged_in=already_logged_in)

        member_id = generate_member_id()
        user = User(
            member_id=member_id,
            email=invitation.email,
            role=invitation.role or Role.MEMBER,
            is_approved=False,   # needs admin approval
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        profile = MemberProfile(
            user_id=user.id,
            full_name=full_name,
            usn=usn,
            branch=branch,
            academic_year=academic_year,
            phone=phone,
            department=invitation.department,
            joined_date=date.today()
        )
        db.session.add(profile)
        invitation.is_used = True
        db.session.commit()

        # Notify admins
        admins = User.query.filter(User.role.in_([Role.ADMIN, Role.RESEARCH_HEAD])).all()
        for admin in admins:
            create_notification(
                admin.id,
                'New Member Pending Approval',
                f'{full_name} just registered and needs your approval to access the portal.',
                'announcement',
                url_for('admin.pending_members')
            )

        log_action('register', 'user', user.id, full_name)
        flash('Account created! An admin will review and approve it. You will be notified.', 'warning')
        return redirect(url_for('auth.signin'))

    return render_template('auth/register.html', invitation=invitation,
                           already_logged_in=already_logged_in)


# ── SET PASSWORD (after admin approves application) ─
@auth_bp.route('/set-password/<token>', methods=['GET', 'POST'])
def set_password(token):
    """Member sets their password after admin approves their application."""
    from app.models import MemberApplication
    app_obj = MemberApplication.query.filter_by(
        set_password_token=token, status='approved'
    ).first()

    if not app_obj:
        flash('Invalid or already used activation link.', 'danger')
        return redirect(url_for('auth.signin'))

    if _is_expired(app_obj.set_password_expires):
        flash('This activation link has expired. Contact the admin for a new one.', 'danger')
        return redirect(url_for('auth.signin'))

    if app_obj.user_id:
        flash('Your account is already activated. Please sign in.', 'info')
        return redirect(url_for('auth.signin'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not is_valid_password(password):
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/set_password.html', token=token, application=app_obj)
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/set_password.html', token=token, application=app_obj)

        # Create the user account
        member_id = generate_member_id()
        user = User(
            member_id=member_id,
            email=app_obj.email,
            role=Role.MEMBER,
            is_active=True,
            is_approved=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Create profile from application data
        profile = MemberProfile(
            user_id=user.id,
            full_name=app_obj.full_name,
            usn=app_obj.usn,
            phone=app_obj.phone,
            branch=app_obj.branch,
            academic_year=app_obj.academic_year,
            department=app_obj.department,
            designation=app_obj.designation or 'Member',
            joined_date=date.today(),
            membership_status='Active'
        )
        db.session.add(profile)

        # Link application to user and clear token
        app_obj.user_id              = user.id
        app_obj.set_password_token   = None
        app_obj.set_password_expires = None
        db.session.commit()

        log_action('account_activated', 'user', user.id, app_obj.email)
        flash('Account activated! You can now sign in.', 'success')
        return redirect(url_for('auth.signin'))

    return render_template('auth/set_password.html', token=token, application=app_obj)


# ── LOGOUT ──────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    log_action('logout', 'user', current_user.id)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


# ── FORGOT PASSWORD ──────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            flash(f'Password reset link: {reset_url}', 'info')
        else:
            flash('If that email exists, a reset link has been generated.', 'info')
    return render_template('auth/forgot_password.html')


# ── RESET PASSWORD ───────────────────────────────
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(password_reset_token=token).first()
    if not user or _is_expired(user.password_reset_expires):
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if not is_valid_password(password):
            flash('Password must be at least 8 characters.', 'danger')
        elif password != confirm:
            flash('Passwords do not match.', 'danger')
        else:
            user.set_password(password)
            user.password_reset_token   = None
            user.password_reset_expires = None
            db.session.commit()
            flash('Password reset! Please sign in.', 'success')
            return redirect(url_for('auth.signin'))

    return render_template('auth/reset_password.html', token=token)
