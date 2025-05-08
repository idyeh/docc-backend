from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt
users_bp = Blueprint("users", __name__)

def role_required(allowed):
    def wrapper(fn):
        @jwt_required()
        def decorator(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get("roles", [])
            if not any(r in allowed for r in user_roles):
                return jsonify(msg="Forbidden"), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

@users_bp.route("/", methods=["GET"])
@role_required(["Administrator", "Super Administrator"])
def list_users():
    from app.models import User
    users = [{"id": u.id, "username": u.username} for u in User.query.all()]
    return jsonify(users=users)
