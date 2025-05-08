from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Role
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, get_jwt_identity
)

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if User.query.filter_by(username=data["username"]).first():
        return jsonify(msg="Username exists"), 409

    user = User(username=data["username"])
    user.set_password(data["password"])
    # default role: Student
    student_role = Role.query.filter_by(name="Student").first()
    user.roles.append(student_role)
    db.session.add(user)
    db.session.commit()
    return jsonify(msg="User created"), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify(msg="Bad credentials"), 401

    additional = {
        "roles":    [r.name for r in user.roles],
        "username": user.username
    }
    access = create_access_token(identity=user.id, additional_claims=additional)
    refresh = create_refresh_token(identity=user.id)
    return jsonify(access_token=access, refresh_token=refresh), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    additional = {"roles": [r.name for r in user.roles]}
    access = create_access_token(identity=uid, additional_claims=additional)
    return jsonify(access_token=access), 200
