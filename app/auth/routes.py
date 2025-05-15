from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Role
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or "username" not in data or "password" not in data:
        return jsonify(msg="Missing username or password"), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify(msg="Username exists"), 409

    user = User(username=data["username"])
    user.set_password(data["password"])

    is_first_user = (User.query.count() == 0)

    if is_first_user:
        admin_role = Role.query.filter_by(name="Administrator").first()
        if not admin_role:
            admin_role = Role(name="Administrator")
            db.session.add(admin_role)
        user.roles.append(admin_role)
        role_assigned_msg = "User created as Administrator."
    else:
        staff_role = Role.query.filter_by(name="Staff").first()
        if not staff_role:
            student_role = Role(name="Staff")
            db.session.add(staff_role)
            db.session.flush()
        if not staff_role:
             return jsonify(msg="Failed to find or create Staff role"), 500
        user.roles.append(staff_role)
        role_assigned_msg = "User created as Staff."

    db.session.add(user)
    db.session.commit()
    return jsonify(msg=role_assigned_msg), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify(msg="Bad credentials"), 401

    additional = {
        "roles": [r.name for r in user.roles],
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
