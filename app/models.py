from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
# from sqlalchemy.dialects.postgresql import JSON

roles_users = db.Table(
    "roles_users",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id")),
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    roles = db.relationship("Role", secondary=roles_users, backref="users")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)

class FormDefinition(db.Model):
    __tablename__ = "form_definition"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_by  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    fields      = db.relationship(
        "FormField",
        backref="form",
        cascade="all, delete-orphan",
        order_by="FormField.order"
    )

class FormField(db.Model):
    __tablename__ = "form_field"
    id         = db.Column(db.Integer, primary_key=True)
    form_id    = db.Column(db.Integer, db.ForeignKey("form_definition.id"), nullable=False)
    name       = db.Column(db.String(64), nullable=False)       # key in JSON
    label      = db.Column(db.String(128), nullable=False)      # human label
    field_type = db.Column(db.String(32), nullable=False)       # text, number, date, dropdown, multiselect, file, richtext
    required   = db.Column(db.Boolean, default=False)
    options    = db.Column(db.JSON, default=[])                    # for dropdown/multiselect: ["Option A","Option B"]
    order      = db.Column(db.Integer, default=0)

class FormEntry(db.Model):
    __tablename__ = "form_entry"
    id         = db.Column(db.Integer, primary_key=True)
    form_id    = db.Column(db.Integer, db.ForeignKey("form_definition.id"), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    data       = db.Column(db.JSON, nullable=False)                # { field.name: value }
    status     = db.Column(db.String(16), default="submitted")  # "draft" or "submitted"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

