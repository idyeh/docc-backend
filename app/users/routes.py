import functools
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db
from app.models import User, Role

users_bp = Blueprint("users", __name__)

def role_required(allowed_roles):
    def decorator_factory(fn):
        @functools.wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get('roles', [])
            if not any(r in allowed_roles for r in user_roles):
                return jsonify(msg='Forbidden'), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator_factory
# GET /api/users?page=1&per_page=10
@users_bp.route('', methods=['GET'])
@role_required(['Administrator', 'Super Administrator'])
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    pagination = User.query.order_by(User.id).paginate(page=page, per_page=per_page, error_out=False)
    data = []
    for u in pagination.items:
        data.append({
            'id': u.id,
            'username': u.username,
            'roles': [r.name for r in u.roles]
        })
    return jsonify(
        users=data,
        page=pagination.page,
        per_page=pagination.per_page,
        total=pagination.total,
        total_pages=pagination.pages
    ), 200

@users_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    """Get current user's information"""
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    
    user = User.query.get_or_404(current_user_id)
    if not user:
        return jsonify(msg="User not found"), 404
    
    return jsonify({
        "id": user.id,
        "username": user.username,
        "roles": claims.get("roles", [])
    })

# GET /api/users/<uid>
@users_bp.route('/<int:uid>', methods=['GET'])
@jwt_required()
def get_user(uid):
    current = get_jwt_identity()
    claims = get_jwt()
    is_admin = any(r in ['Administrator','Super Administrator'] for r in claims.get('roles', []))
    if uid != current and not is_admin:
        return jsonify(msg='Forbidden'), 403
    user = User.query.get_or_404(uid)
    return jsonify(
        id=user.id,
        username=user.username,
        roles=[r.name for r in user.roles]
    ), 200

# POST /api/users
@users_bp.route('', methods=['POST'])
@role_required(['Administrator', 'Super Administrator'])
def create_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    roles = data.get('roles', [])
    if User.query.filter_by(username=username).first():
        return jsonify(msg='Username already exists'), 400
    user = User(username=username)
    user.set_password(password)
    # assign roles
    for role_name in roles:
        role = Role.query.filter_by(name=role_name).first()
        if role:
            user.roles.append(role)
    db.session.add(user)
    db.session.commit()
    return jsonify(id=user.id), 201

# PUT /api/users/<uid>
@users_bp.route('/<int:uid>', methods=['PUT'])
@jwt_required()
def update_user(uid):
    current = get_jwt_identity()
    claims  = get_jwt()
    user    = User.query.get_or_404(uid)
    # Only the user themselves or an admin can update
    is_self  = (current == uid)
    is_admin = any(r.name in ['Administrator','Super Administrator'] for r in user.roles) \
               or any(r in claims.get('roles', []) for r in ['Administrator','Super Administrator'])
    if not (is_self or is_admin):
        return jsonify(msg="Forbidden"), 403

    data = request.get_json()
    if 'username' in data:
        user.username = data['username']
    if 'password' in data:
        user.set_password(data['password'])

    # Update roles (only admins)
    if is_admin and 'roles' in data:
        # Expecting data['roles'] to be a list of role names
        if not isinstance(data['roles'], list) or not all(isinstance(r, str) for r in data['roles']):
            return jsonify(msg="Invalid roles format"), 400
        roles = Role.query.filter(Role.name.in_(data['roles'])).all()
        existing_names = {r.name for r in roles}
        missing = set(data['roles']) - existing_names
        if missing:
            return jsonify(msg=f"Unknown roles: {', '.join(missing)}"), 400

        user.roles = roles

    db.session.commit()
    return jsonify(msg="User updated"), 200

# DELETE /api/users/<uid>
@users_bp.route('/<int:uid>', methods=['DELETE'])
@jwt_required()
def delete_user(uid):
    current = get_jwt_identity()
    claims = get_jwt()
    is_admin = any(r in ['Administrator','Super Administrator'] for r in claims.get('roles', []))
    if uid != current and not is_admin:
        return jsonify(msg='Forbidden'), 403
    user = User.query.get_or_404(uid)
    db.session.delete(user)
    db.session.commit()
    return jsonify(msg='User deleted'), 200
