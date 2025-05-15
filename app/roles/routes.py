from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app import db
from app.models import Role

roles_bp = Blueprint('roles', __name__)

def role_required(allowed_roles):
    def decorator(fn):
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get('roles', [])
            if not any(r in user_roles for r in allowed_roles):
                return jsonify(msg='Forbidden'), 403
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator

@roles_bp.route('', methods=['GET'])
@role_required(['Administrator', 'Super Administrator'])
def list_roles():
    roles = Role.query.order_by(Role.name).all()
    return jsonify(roles=[{'id': r.id, 'name': r.name} for r in roles]), 200

@roles_bp.route('/<int:role_id>', methods=['GET'])
@role_required(['Administrator', 'Super Administrator'])
def get_role(role_id):
    role = Role.query.get_or_404(role_id)
    return jsonify(id=role.id, name=role.name), 200

@roles_bp.route('', methods=['POST'])
@role_required(['Administrator', 'Super Administrator'])
def create_role():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify(msg='Role name is required'), 400
    if Role.query.filter_by(name=name).first():
        return jsonify(msg='Role already exists'), 400

    role = Role(name=name)
    db.session.add(role)
    db.session.commit()
    return jsonify(id=role.id, name=role.name), 201

@roles_bp.route('/<int:role_id>', methods=['PUT'])
@role_required(['Administrator', 'Super Administrator'])
def update_role(role_id):
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify(msg='Role name is required'), 400

    role = Role.query.get_or_404(role_id)
    # prevent duplicate names
    if Role.query.filter(Role.name == name, Role.id != role_id).first():
        return jsonify(msg='Another role with that name already exists'), 400

    role.name = name
    db.session.commit()
    return jsonify(msg='Role updated'), 200

@roles_bp.route('/<int:role_id>', methods=['DELETE'])
@role_required(['Administrator', 'Super Administrator'])
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    db.session.delete(role)
    db.session.commit()
    return jsonify(msg='Role deleted'), 200
