from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime, timezone
import secrets


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─────────────────────────────────────────────
# ENUMS / CONSTANTS
# ─────────────────────────────────────────────
class Role:
    MEMBER = 'member'
    PROJECT_LEAD = 'project_lead'
    RESEARCH_HEAD = 'research_head'
    ADMIN = 'admin'

class Department:
    RESEARCH = 'Research & Projects'
    WEBMASTER = 'Webmaster'
    TECHNICAL = 'Technical Team'
    SOCIAL = 'Social Media'
    PR = 'Public Relations'
    EVENTS = 'Event Management'

class ProjectStatus:
    PLANNING = 'Planning'
    RESEARCH = 'Research'
    DEVELOPMENT = 'Development'
    TESTING = 'Testing'
    REVIEW = 'Under Review'
    COMPLETED = 'Completed'
    ON_HOLD = 'On Hold'

class TaskStatus:
    TODO = 'To Do'
    IN_PROGRESS = 'In Progress'
    REVIEW = 'Under Review'
    COMPLETED = 'Completed'

class TaskPriority:
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'
    URGENT = 'Urgent'


# ─────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default=Role.MEMBER)
    is_active = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=False)  # Members need admin approval
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    password_reset_token = db.Column(db.String(100))
    password_reset_expires = db.Column(db.DateTime)

    # Relationship to profile
    profile = db.relationship('MemberProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        from app import bcrypt
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        from app import bcrypt
        return bcrypt.check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role in [Role.ADMIN, Role.RESEARCH_HEAD]

    def is_project_lead(self):
        return self.role in [Role.PROJECT_LEAD, Role.ADMIN, Role.RESEARCH_HEAD]

    def generate_reset_token(self):
        self.password_reset_token = secrets.token_urlsafe(32)
        from datetime import timedelta
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        return self.password_reset_token

    def __repr__(self):
        return f'<User {self.email}>'


# ─────────────────────────────────────────────
# INVITATION
# ─────────────────────────────────────────────
class Invitation(db.Model):
    __tablename__ = 'invitations'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)   # NOT unique — one person can be re-invited
    token = db.Column(db.String(100), unique=True, nullable=False)  # token is unique
    role = db.Column(db.String(30), default=Role.MEMBER)
    department = db.Column(db.String(50))
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)


# ─────────────────────────────────────────────
# MEMBER PROFILE
# ─────────────────────────────────────────────
class MemberProfile(db.Model):
    __tablename__ = 'member_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    # Personal info
    full_name = db.Column(db.String(100), nullable=False)
    usn = db.Column(db.String(20))
    phone = db.Column(db.String(15))
    profile_picture = db.Column(db.String(200), default='default_avatar.png')

    # Academic info
    branch = db.Column(db.String(50))
    academic_year = db.Column(db.String(10))
    college = db.Column(db.String(100), default='Your College')

    # Club info
    department = db.Column(db.String(50))
    designation = db.Column(db.String(50))
    joined_date = db.Column(db.Date)
    membership_status = db.Column(db.String(20), default='Active')

    # Skills & interests
    technical_skills = db.Column(db.Text)
    areas_of_interest = db.Column(db.Text)

    # Links
    github_url = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(200))
    portfolio_url = db.Column(db.String(200))

    # Stats (computed but cached)
    contribution_points = db.Column(db.Integer, default=0)

    bio = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<MemberProfile {self.full_name}>'


# ─────────────────────────────────────────────
# PROJECT
# ─────────────────────────────────────────────
project_members = db.Table('project_members',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow)
)

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    problem_statement = db.Column(db.Text)
    proposed_solution = db.Column(db.Text)
    objectives = db.Column(db.Text)
    technologies = db.Column(db.Text)

    lead_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    department = db.Column(db.String(50))

    status = db.Column(db.String(30), default=ProjectStatus.PLANNING)
    visibility = db.Column(db.String(20), default='private')
    progress_percent = db.Column(db.Integer, default=0)

    start_date = db.Column(db.Date)
    expected_end_date = db.Column(db.Date)
    completed_date = db.Column(db.Date)

    github_url = db.Column(db.String(200))
    demo_url = db.Column(db.String(200))

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead = db.relationship('User', foreign_keys=[lead_id], backref='led_projects')
    creator = db.relationship('User', foreign_keys=[created_by])
    members = db.relationship('User', secondary=project_members, backref='projects')
    tasks = db.relationship('Task', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    milestones = db.relationship('Milestone', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    meetings = db.relationship('Meeting', backref='project', lazy='dynamic')
    documents = db.relationship('Document', backref='project', lazy='dynamic')
    progress_reports = db.relationship('WeeklyReport', backref='project', lazy='dynamic')

    def __repr__(self):
        return f'<Project {self.title}>'


# ─────────────────────────────────────────────
# MILESTONE
# ─────────────────────────────────────────────
class Milestone(db.Model):
    __tablename__ = 'milestones'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# TASK
# ─────────────────────────────────────────────
class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestones.id'))

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default=TaskPriority.MEDIUM)
    status = db.Column(db.String(30), default=TaskStatus.TODO)
    reference_materials = db.Column(db.Text)

    due_date = db.Column(db.Date)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assignee = db.relationship('User', foreign_keys=[assignee_id], backref='assigned_tasks')
    creator = db.relationship('User', foreign_keys=[created_by])
    submissions = db.relationship('TaskSubmission', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('TaskComment', backref='task', lazy='dynamic', cascade='all, delete-orphan')

    def is_overdue(self):
        if self.due_date and self.status != TaskStatus.COMPLETED:
            return datetime.now(timezone.utc).date() > self.due_date
        return False

    def __repr__(self):
        return f'<Task {self.title}>'


class TaskSubmission(db.Model):
    __tablename__ = 'task_submissions'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submission_notes = db.Column(db.Text)
    submission_link = db.Column(db.String(300))
    file_path = db.Column(db.String(300))
    status = db.Column(db.String(20), default='Submitted')  # Submitted, Approved, Rejected, Revision
    reviewer_notes = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)

    submitter = db.relationship('User', foreign_keys=[submitted_by])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])


class TaskComment(db.Model):
    __tablename__ = 'task_comments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', backref='task_comments')


# ─────────────────────────────────────────────
# RESEARCH
# ─────────────────────────────────────────────
class ResearchPaper(db.Model):
    __tablename__ = 'research_papers'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    authors = db.Column(db.String(300))
    source = db.Column(db.String(200))
    publication_date = db.Column(db.Date)
    publication_link = db.Column(db.String(400))
    research_topic = db.Column(db.String(200))
    methodology = db.Column(db.Text)
    key_findings = db.Column(db.Text)
    research_gaps = db.Column(db.Text)
    references = db.Column(db.Text)
    notes = db.Column(db.Text)
    file_path = db.Column(db.String(300))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_researcher = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', foreign_keys=[uploaded_by], backref='uploaded_papers')
    researcher = db.relationship('User', foreign_keys=[assigned_researcher])
    project = db.relationship('Project', backref='research_papers')


# ─────────────────────────────────────────────
# MEETING
# ─────────────────────────────────────────────
meeting_participants = db.Table('meeting_participants',
    db.Column('meeting_id', db.Integer, db.ForeignKey('meetings.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

class Meeting(db.Model):
    __tablename__ = 'meetings'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    meeting_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    venue = db.Column(db.String(200))
    meeting_link = db.Column(db.String(400))
    meeting_type = db.Column(db.String(30), default='team')  # team, project, general, one-on-one
    agenda = db.Column(db.Text)
    minutes = db.Column(db.Text)
    decisions = db.Column(db.Text)
    follow_up_tasks = db.Column(db.Text)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    organized_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    organizer = db.relationship('User', foreign_keys=[organized_by], backref='organized_meetings')
    participants = db.relationship('User', secondary=meeting_participants, backref='meetings')


# ─────────────────────────────────────────────
# WEEKLY REPORT
# ─────────────────────────────────────────────
class WeeklyReport(db.Model):
    __tablename__ = 'weekly_reports'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    week_end = db.Column(db.Date, nullable=False)

    work_completed = db.Column(db.Text)
    tasks_completed = db.Column(db.Text)
    current_work = db.Column(db.Text)
    challenges = db.Column(db.Text)
    research_progress = db.Column(db.Text)
    next_week_goals = db.Column(db.Text)
    assistance_required = db.Column(db.Text)
    supporting_links = db.Column(db.Text)

    status = db.Column(db.String(20), default='Submitted')  # Submitted, Reviewed
    feedback = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', foreign_keys=[user_id], backref='weekly_reports')
    reviewer_user = db.relationship('User', foreign_keys=[reviewed_by])


# ─────────────────────────────────────────────
# ANNOUNCEMENT
# ─────────────────────────────────────────────
class Announcement(db.Model):
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    priority = db.Column(db.String(20), default='Normal')
    target_department = db.Column(db.String(50))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

    author = db.relationship('User', foreign_keys=[posted_by], backref='announcements')


# ─────────────────────────────────────────────
# DOCUMENT
# ─────────────────────────────────────────────
class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    category = db.Column(db.String(50))
    access_level = db.Column(db.String(20), default='project')  # public, project, admin
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', foreign_keys=[uploaded_by], backref='uploaded_documents')


# ─────────────────────────────────────────────
# ACHIEVEMENT
# ─────────────────────────────────────────────
class Achievement(db.Model):
    __tablename__ = 'achievements'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # project, research, competition, workshop, etc.
    points = db.Column(db.Integer, default=0)
    badge_icon = db.Column(db.String(50))
    certificate_path = db.Column(db.String(300))
    awarded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_verified = db.Column(db.Boolean, default=False)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)

    member = db.relationship('User', foreign_keys=[user_id], backref='achievements')
    awarder = db.relationship('User', foreign_keys=[awarded_by])


# ─────────────────────────────────────────────
# NOTIFICATION
# ─────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    notif_type = db.Column(db.String(50))  # task, project, meeting, announcement, achievement
    link = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# AUDIT LOG
# ─────────────────────────────────────────────
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# CHANGE REQUEST (Content Approval Workflow)
# ─────────────────────────────────────────────
class ChangeRequest(db.Model):
    __tablename__ = 'change_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_type = db.Column(db.String(50), nullable=False)  # profile, project, announcement, etc.
    target_id = db.Column(db.Integer)
    action = db.Column(db.String(30), nullable=False)  # update, create, delete
    field_changes = db.Column(db.Text)  # JSON of changed fields {field: {old, new}}
    description = db.Column(db.Text)  # user's description of what they changed and why
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    admin_notes = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)

    requester = db.relationship('User', foreign_keys=[user_id], backref='change_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<ChangeRequest {self.action} {self.target_type} by {self.user_id}>'


# ─────────────────────────────────────────────
# GALLERY
# ─────────────────────────────────────────────
class GalleryAlbum(db.Model):
    __tablename__ = 'gallery_albums'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(300))        # path to cover photo
    event_date  = db.Column(db.Date)
    category    = db.Column(db.String(50))         # Events, Workshop, Hackathon, etc.
    is_published = db.Column(db.Boolean, default=False)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by], backref='gallery_albums')
    photos  = db.relationship('GalleryPhoto', backref='album',
                              lazy='dynamic', cascade='all, delete-orphan',
                              order_by='GalleryPhoto.position')

    def photo_count(self):
        return self.photos.count()

    def __repr__(self):
        return f'<GalleryAlbum {self.title}>'


class GalleryPhoto(db.Model):
    __tablename__ = 'gallery_photos'

    id          = db.Column(db.Integer, primary_key=True)
    album_id    = db.Column(db.Integer, db.ForeignKey('gallery_albums.id'), nullable=False)
    file_path   = db.Column(db.String(300), nullable=False)
    caption     = db.Column(db.String(300))
    credit      = db.Column(db.String(100))        # photographer credit
    position    = db.Column(db.Integer, default=0) # order within album
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def __repr__(self):
        return f'<GalleryPhoto {self.file_path}>'


# ─────────────────────────────────────────────
# MEMBER APPLICATION (public self-apply)
# ─────────────────────────────────────────────
class MemberApplication(db.Model):
    __tablename__ = 'member_applications'

    id            = db.Column(db.Integer, primary_key=True)
    full_name     = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), nullable=False)
    usn           = db.Column(db.String(20))
    phone         = db.Column(db.String(15))
    branch        = db.Column(db.String(50))
    academic_year = db.Column(db.String(20))
    department    = db.Column(db.String(50))
    designation   = db.Column(db.String(50))
    reason        = db.Column(db.Text)

    # Workflow
    status        = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    admin_notes   = db.Column(db.Text)
    reviewed_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at   = db.Column(db.DateTime)

    # Once approved, a set-password token is generated
    set_password_token   = db.Column(db.String(100))
    set_password_expires = db.Column(db.DateTime)

    # Link to created user account (set after approval + password setup)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'))

    submitted_at  = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    user     = db.relationship('User', foreign_keys=[user_id])

    def generate_set_password_token(self):
        import secrets as _s
        from datetime import timedelta
        self.set_password_token   = _s.token_urlsafe(32)
        self.set_password_expires = datetime.utcnow() + timedelta(days=3)
        return self.set_password_token

    def __repr__(self):
        return f'<MemberApplication {self.email}>'
