import databases
import sqlalchemy
from doccapi.config import config

engine = sqlalchemy.create_engine(config.DATABASE_URL)
metadata = sqlalchemy.MetaData()


user_table = sqlalchemy.Table(
    "user",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("email", sqlalchemy.String, unique=True),
    sqlalchemy.Column("password", sqlalchemy.String),
    sqlalchemy.Column("username", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("password_hash", sqlalchemy.String,nullable=False),
    sqlalchemy.Column("confirmed", sqlalchemy.Boolean, default=False),
)

user_role_table = sqlalchemy.Table(
    "user_role",
    metadata,
    sqlalchemy.Column("user_id", sqlalchemy.ForeignKey("user.id"), primary_key=True),
    sqlalchemy.Column("role_id", sqlalchemy.ForeignKey("roles.id"), primary_key=True),
)

role_table = sqlalchemy.Table(
    "roles",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(64), unique=True, nullable=False),
)

userprofile_table = sqlalchemy.Table(
    "user_profile",
    metadata,
    sqlalchemy.Column("user_id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("full_name", sqlalchemy.String, unique=False, nullable=False),
    sqlalchemy.Column("avatar_url", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("bio", sqlalchemy.Text, nullable=True),
)

staffprofile_table = sqlalchemy.Table(
    "staff_profile",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("department", sqlalchemy.String(128)),
    sqlalchemy.Column("expertise", sqlalchemy.Text),
    sqlalchemy.Column("contact", sqlalchemy.String(256)),
)

studentprofile_table = sqlalchemy.Table(
    "student_profile",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("program", sqlalchemy.String(128)),
    sqlalchemy.Column("class_year", sqlalchemy.Text),
    sqlalchemy.Column("advisor", sqlalchemy.String(256)),
)   

# 添加新的表定义
timeschedule_table = sqlalchemy.Table(
    "time_schedule",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("owner_id", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("type", sqlalchemy.String(32)),  # course, event, meeting, booking
    sqlalchemy.Column("start", sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column("end", sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column("location", sqlalchemy.String(256)),
)

award_table = sqlalchemy.Table(
    "award",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("recipient_id", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("name", sqlalchemy.String(256), nullable=False),
    sqlalchemy.Column("date", sqlalchemy.Date, nullable=False),
    sqlalchemy.Column("awarding_body", sqlalchemy.String(256)),
)

achievement_table = sqlalchemy.Table(
    "achievement",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("owner_id", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("title", sqlalchemy.String(256), nullable=False),
    sqlalchemy.Column("description", sqlalchemy.Text),
)

mediafile_table = sqlalchemy.Table(
    "media_file",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("filename", sqlalchemy.String(256), nullable=False),
    sqlalchemy.Column("content_type", sqlalchemy.String(128), nullable=False),
    sqlalchemy.Column("url", sqlalchemy.String(512), nullable=False),
    sqlalchemy.Column("size", sqlalchemy.Integer),
    sqlalchemy.Column("meta", sqlalchemy.JSON),
    sqlalchemy.Column("uploaded_by", sqlalchemy.ForeignKey("user.id")),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=sqlalchemy.func.now()),
    sqlalchemy.Column("version", sqlalchemy.Integer, default=1),
)

researchpaper_table = sqlalchemy.Table(
    "research_paper",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("title", sqlalchemy.String(256), nullable=False),
    sqlalchemy.Column("authors", sqlalchemy.String(512)),
    sqlalchemy.Column("abstract", sqlalchemy.Text),
    sqlalchemy.Column("publication_date", sqlalchemy.Date),
    sqlalchemy.Column("journal", sqlalchemy.String(256)),
    sqlalchemy.Column("doi", sqlalchemy.String(128)),
    sqlalchemy.Column("owner_id", sqlalchemy.ForeignKey("user.id")),
    sqlalchemy.Column("file_id", sqlalchemy.ForeignKey("media_file.id")),
)

patent_table = sqlalchemy.Table(
    "patent",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("title", sqlalchemy.String(256), nullable=False),
    sqlalchemy.Column("inventors", sqlalchemy.String(512)),
    sqlalchemy.Column("patent_number", sqlalchemy.String(128), nullable=False),
    sqlalchemy.Column("date", sqlalchemy.Date),
    sqlalchemy.Column("abstract", sqlalchemy.Text),
    sqlalchemy.Column("owner_id", sqlalchemy.ForeignKey("user.id")),
    sqlalchemy.Column("file_id", sqlalchemy.ForeignKey("media_file.id")),
)

# event with meida (many-to-many)
event_media_table = sqlalchemy.Table(
    "event_media",
    metadata,
    sqlalchemy.Column("event_id", sqlalchemy.ForeignKey("event_log.id"), primary_key=True),
    sqlalchemy.Column("media_id", sqlalchemy.ForeignKey("media_file.id"), primary_key=True),
)

eventlog_table = sqlalchemy.Table(
    "event_log",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(256), nullable=False),
    sqlalchemy.Column("date", sqlalchemy.DateTime, default=sqlalchemy.func.now()),
    sqlalchemy.Column("location", sqlalchemy.String(256)),
    sqlalchemy.Column("description", sqlalchemy.Text),
    sqlalchemy.Column("attendees", sqlalchemy.JSON),  # list of user IDs
)

workflowdefinition_table = sqlalchemy.Table(
    "workflow_definition",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(256), nullable=False, unique=True),
    sqlalchemy.Column("steps", sqlalchemy.JSON, nullable=False), # list of objects: [{ name, assign_roles:[...], assign_users:[...] }, ...]
)

workflowinstance_table = sqlalchemy.Table(
    "workflow_instance",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("workflow_id", sqlalchemy.ForeignKey("workflow_definition.id"), nullable=False),
    sqlalchemy.Column("user_id", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("entity_type", sqlalchemy.String(64), nullable=False), # e.g, 'form', 'project', etc.
    sqlalchemy.Column("entity_id", sqlalchemy.Integer, nullable=False), # e.g, form_id, etc.
    sqlalchemy.Column("current_step", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("state", sqlalchemy.String(64)), # Definition.steps[current_step]['name']
    sqlalchemy.Column("logs", sqlalchemy.JSON, default=[]),
     # history: [{by, step, timestamp, comment}, ...]
    sqlalchemy.UniqueConstraint(
        'workflow_id', 'entity_type', 'entity_id', 'user_id',
        name='uq_workflow_instance_unique_per_user'
    ),
)

notification_table = sqlalchemy.Table(
    "notification",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("message", sqlalchemy.String(512), nullable=False),
    sqlalchemy.Column("url", sqlalchemy.String(256)),
    sqlalchemy.Column("is_read", sqlalchemy.Boolean, default=False),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=sqlalchemy.func.now()),
)

formdefinition_table = sqlalchemy.Table(
    "form_definition",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(128), nullable=False, unique=True),
    sqlalchemy.Column("description", sqlalchemy.Text),
    sqlalchemy.Column("created_by", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=sqlalchemy.func.now()),
)

formfield_table = sqlalchemy.Table(
    "form_field",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("form_id", sqlalchemy.ForeignKey("form_definition.id"), nullable=False),
    sqlalchemy.Column("name", sqlalchemy.String(64), nullable=False),
    sqlalchemy.Column("label", sqlalchemy.String(128), nullable=False),
    sqlalchemy.Column("field_type", sqlalchemy.String(32), nullable=False),
    sqlalchemy.Column("required", sqlalchemy.Boolean, default=False),
    sqlalchemy.Column("options", sqlalchemy.JSON, default=[]),
    sqlalchemy.Column("order", sqlalchemy.Integer, default=0),
)

formentry_table = sqlalchemy.Table(
    "form_entry",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("form_id", sqlalchemy.ForeignKey("form_definition.id"), nullable=False),
    sqlalchemy.Column("user_id", sqlalchemy.ForeignKey("user.id"), nullable=False),
    sqlalchemy.Column("data", sqlalchemy.JSON, nullable=False),
    sqlalchemy.Column("status", sqlalchemy.String(16), default="submitted"),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=sqlalchemy.func.now()),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime, onupdate=sqlalchemy.func.now()),
)


engine = sqlalchemy.create_engine(
    config.DATABASE_URL, connect_args={"check_same_thread": False}
)

metadata.create_all(engine)
database = databases.Database(
    config.DATABASE_URL, force_rollback=config.DB_FORCE_ROLL_BACK
)
