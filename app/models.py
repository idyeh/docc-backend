from datetime import datetime
from uuid import uuid4
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
# from sqlalchemy.dialects.postgresql import JSON

# Association tables
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)

event_media = db.Table(
    'event_media',
    db.Column('event_id', db.Integer, db.ForeignKey('event_log.id'), primary_key=True),
    db.Column('media_id', db.Integer, db.ForeignKey('media_file.id'), primary_key=True)
)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    roles = db.relationship('Role', secondary=roles_users, backref='users')
    profile = db.relationship('UserProfile', uselist=False, backref='user')
    uploaded_files = db.relationship('MediaFile', backref='uploader')
    # relationships for convenience
    papers = db.relationship('ResearchPaper', backref='owner')
    patents = db.relationship('Patent', backref='owner')
    awards = db.relationship('Award', backref='recipient')
    achievements = db.relationship('Achievement', backref='owner')
    schedules = db.relationship('TimeSchedule', backref='owner')

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)

class UserProfile(db.Model):
    __tablename__ = 'user_profile'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    full_name = db.Column(db.String(128))
    avatar_url = db.Column(db.String(256))
    bio = db.Column(db.Text)

class StaffProfile(db.Model):
    __tablename__ = 'staff_profile'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department = db.Column(db.String(128))
    expertise = db.Column(db.Text)
    contact = db.Column(db.String(256))

class StudentProfile(db.Model):
    __tablename__ = 'student_profile'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program = db.Column(db.String(128))
    year = db.Column(db.Integer)
    advisor = db.Column(db.String(128))

class TimeSchedule(db.Model):
    __tablename__ = 'time_schedule'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(32))  # e.g. course, event, meeting, booking
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(256))

class Award(db.Model):
    __tablename__ = 'award'
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    date = db.Column(db.Date, nullable=False)
    awarding_body = db.Column(db.String(256))

class Achievement(db.Model):
    __tablename__ = 'achievement'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)

class MediaFile(db.Model):
    __tablename__ = 'media_file'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    content_type = db.Column(db.String(128), nullable=False)
    url = db.Column(db.String(512), nullable=False)
    size = db.Column(db.Integer)
    meta = db.Column(db.JSON)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    version = db.Column(db.Integer, default=1)

class ResearchPaper(db.Model):
    __tablename__ = 'research_paper'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    authors = db.Column(db.String(512))
    abstract = db.Column(db.Text)
    publication_date = db.Column(db.Date)
    journal = db.Column(db.String(256))
    doi = db.Column(db.String(128))
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    file_id = db.Column(db.Integer, db.ForeignKey('media_file.id'))
    file = db.relationship('MediaFile')

class Patent(db.Model):
    __tablename__ = 'patent'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    inventors = db.Column(db.String(512))
    patent_number = db.Column(db.String(128), nullable=False)
    date = db.Column(db.Date)
    abstract = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    file_id = db.Column(db.Integer, db.ForeignKey('media_file.id'))
    file = db.relationship('MediaFile')

class EventLog(db.Model):
    __tablename__ = 'event_log'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    location = db.Column(db.String(256))
    description = db.Column(db.Text)
    attendees = db.Column(db.JSON)  # list of user IDs
    media = db.relationship('MediaFile', secondary=event_media)

class WorkflowDefinition(db.Model):
    __tablename__ = 'workflow_definition'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    steps = db.Column(db.JSON)  # e.g. ["submit", "approve", ...]

class WorkflowInstance(db.Model):
    __tablename__ = 'workflow_instance'
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_definition.id'))
    entity_type = db.Column(db.String(64))  # e.g. "form_entry"
    entity_id = db.Column(db.Integer)       # e.g. FormEntry.id
    state = db.Column(db.String(64))        # current step name
    logs = db.Column(db.JSON)               # history of transitions

class FormDefinition(db.Model):
    __tablename__ = 'form_definition'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    fields = db.relationship(
        'FormField', backref='form', cascade='all, delete-orphan', order_by='FormField.order'
    )

class FormField(db.Model):
    __tablename__ = 'form_field'
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('form_definition.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    label = db.Column(db.String(128), nullable=False)
    field_type = db.Column(db.String(32), nullable=False)
    required = db.Column(db.Boolean, default=False)
    options = db.Column(db.JSON, default=[])
    order = db.Column(db.Integer, default=0)

class FormEntry(db.Model):
    __tablename__ = 'form_entry'
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('form_definition.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(16), default='submitted')  # 'draft' or 'submitted'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
