import functools
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db
from app.models import FormDefinition, FormField, FormEntry, WorkflowDefinition, WorkflowInstance

forms_bp = Blueprint("forms", __name__)

def user_is_admin():
    claims = get_jwt()
    roles = claims.get("roles", [])
    return "Super Administrator" in roles or "Administrator" in roles

def role_required(allowed_roles):
    """
    Decorator factory: only allow users whose JWT 'roles' claim
    contains at least one of `allowed_roles`.
    """
    def decorator_factory(fn):
        @functools.wraps(fn)  # preserves fn.__name__ so Flask endpoints stay unique
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get("roles", [])
            if not any(r in allowed_roles for r in user_roles):
                return jsonify(msg="Forbidden"), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator_factory

@forms_bp.route("/", methods=["POST"])
@role_required(["Super Administrator", "Administrator"])
def create_form():
    """
    Payload:
    {
      "name": "Research Paper Submission",
      "description": "...",
      "fields": [
        { "name":"title","label":"Title","field_type":"text","required":true,"order":1 },
        { "name":"abstract","label":"Abstract","field_type":"richtext","required":true,"order":2 },
        { "name":"pdf","label":"Upload PDF","field_type":"file","required":true,"order":3 }
      ]
    }
    """
    data = request.get_json()
    form = FormDefinition(
      name=data["name"],
      description=data.get("description",""),
      created_by=get_jwt_identity()
    )
    for f in data["fields"]:
        form.fields.append(FormField(**f))
    db.session.add(form)
    db.session.commit()
    return jsonify(id=form.id), 201

@forms_bp.route("/<int:fid>", methods=["GET"])
@jwt_required()
def get_form(fid):
    f = FormDefinition.query.get_or_404(fid)
    uid  = get_jwt_identity()

    if not user_is_admin():
        has_entry = FormEntry.query.filter_by(
                        form_id=fid, user_id=uid
                    ).first() is not None

        assigned = False
        for inst in WorkflowInstance.query.filter_by(user_id=uid):
            wdef = WorkflowDefinition.query.get(inst.workflow_id)
            for step in wdef.steps:
                if step.get("form_id")==fid \
                   and (uid in step.get("assign_users",[]) \
                        or any(r in get_jwt().get("roles",[]) for r in step.get("assign_roles",[]))):
                    assigned = True
                    break
            if assigned:
                break

        if not (has_entry or assigned):
            return jsonify(msg="Forbidden"), 403
    
    return jsonify({
      "id": f.id,
      "name": f.name,
      "description": f.description,
      "fields": [
        {
          "id": fld.id,
          "name": fld.name,
          "label": fld.label,
          "field_type": fld.field_type,
          "required": fld.required,
          "options": fld.options,
          "order": fld.order
        }
        for fld in f.fields
      ]
    }), 200

@forms_bp.route("/<int:fid>", methods=["PUT"])
@role_required(["Super Administrator", "Administrator"])
def update_form(fid):
    data = request.get_json()
    f = FormDefinition.query.get_or_404(fid)
    f.name = data.get("name", f.name)
    f.description = data.get("description", f.description)
    # naive fields replace: delete old, add new
    FormField.query.filter_by(form_id=fid).delete()
    for fld in data["fields"]:
        f.fields.append(FormField(**fld))
    db.session.commit()
    return jsonify(msg="Updated"), 200

@forms_bp.route("/<int:fid>/entries", methods=["POST"])
@jwt_required()
def submit_entry(fid):
    """
    Payload:
    {
      "data": { "title":"...", "abstract":"...", "pdf":<file-id or URL> },
      "status": "draft"  # or "submitted"
    }
    """
    payload = request.get_json()
    entry = FormEntry(
      form_id=fid,
      user_id=get_jwt_identity(),
      data=payload["data"],
      status=payload.get("status","submitted")
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify(id=entry.id), 201

@forms_bp.route("/entries/<int:eid>", methods=["PUT"])
@jwt_required()
def update_entry(eid):
    entry = FormEntry.query.get_or_404(eid)
    if entry.user_id != get_jwt_identity():
        return jsonify(msg="Forbidden"), 403
    data = request.get_json()
    entry.data = data["data"]
    entry.status = data.get("status", entry.status)
    db.session.commit()
    return jsonify(msg="Updated"), 200

@forms_bp.route("/<int:fid>/entries/mine", methods=["GET"])
@jwt_required()
def list_my_entries(fid):
    uid = get_jwt_identity()
    entries = FormEntry.query.filter_by(form_id=fid, user_id=uid).all()
    return jsonify([
      { "id": e.id, "data": e.data, "status": e.status, "updated_at": e.updated_at }
      for e in entries
    ]), 200

@forms_bp.route("/<int:fid>/entries", methods=["GET"])
@role_required(["Super Administrator", "Administrator"])
def list_all_entries(fid):
    entries = FormEntry.query.filter_by(form_id=fid).all()
    return jsonify([
      { "id": e.id, "user_id": e.user_id, "data": e.data, "status": e.status }
      for e in entries
    ]), 200

@forms_bp.route("", methods=["GET"])
@jwt_required()
def list_forms():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    if user_is_admin():
        q = FormDefinition.query
    else:
        uid = get_jwt_identity()
        roles = get_jwt().get("roles", [])

        # 1) Forms the user has already submitted
        entry_rows = (
            db.session.query(FormEntry.form_id)
                      .filter_by(user_id=uid)
                      .distinct()
                      .all()
        )
        entry_ids = [fid for (fid,) in entry_rows]

        # 2) Forms assigned in any existing workflow definition
        assigned_ids = []
        for wdef in WorkflowDefinition.query.all():
            for step in wdef.steps:
                # only consider this step if the user or one of their roles is listed
                if (
                    uid in step.get("assign_users", [])
                    or any(r in roles for r in step.get("assign_roles", []))
                ):
                    fid = step.get("form_id")
                    if isinstance(fid, int):
                        assigned_ids.append(fid)

        allowed_ids = set(entry_ids) | set(assigned_ids)

        # If they have no allowed IDs, return an empty page
        if not allowed_ids:
            return jsonify({
                "forms":       [],
                "page":        page,
                "per_page":    per_page,
                "total":       0,
                "total_pages": 0
            }), 200

        q = FormDefinition.query.filter(
            FormDefinition.id.in_(allowed_ids)
        )

    pagination = (
        q.order_by(FormDefinition.created_at.desc())
         .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        "forms": [
            {"id": f.id, "name": f.name, "description": f.description}
            for f in pagination.items
        ],
        "page":        pagination.page,
        "per_page":    pagination.per_page,
        "total":       pagination.total,
        "total_pages": pagination.pages
    }), 200

@forms_bp.route("/<int:fid>", methods=["DELETE"])
@role_required(["Super Administrator", "Administrator"])
def delete_form(fid):
    """
    DELETE /api/forms/123
    Only allowed if no entries have been submitted for this form.
    """
    count = FormEntry.query.filter_by(form_id=fid).count()
    if count > 0:
        return jsonify(msg="Cannot delete: entries exist"), 400

    form = FormDefinition.query.get_or_404(fid)
    db.session.delete(form)
    db.session.commit()
    return jsonify(msg="Form deleted"), 200


@forms_bp.route("/entries/<int:eid>", methods=["DELETE"])
@jwt_required()
def delete_entry(eid):
    """
    DELETE /api/forms/entries/456
    Users can delete their own drafts/submissions;
    Admins can delete any entry.
    """
    entry = FormEntry.query.get_or_404(eid)
    uid   = get_jwt_identity()
    roles = get_jwt().get("roles", [])

    # only owner or admin
    if entry.user_id != uid and not any(r in ["Super Administrator", "Administrator"] for r in roles):
        return jsonify(msg="Forbidden"), 403

    db.session.delete(entry)
    db.session.commit()
    return jsonify(msg="Entry deleted"), 200