from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db
from app.models import WorkflowDefinition, WorkflowInstance, Notification

workflows_bp = Blueprint('workflows', __name__)

# --- Admin: CRUD on workflow templates ---
@workflows_bp.route('', methods=['GET'])
@jwt_required()
def list_definitions():
    claims = get_jwt()
    if 'Administrator' not in claims.get('roles', []):
        return jsonify(msg='Forbidden'), 403
    defs = WorkflowDefinition.query.all()
    return jsonify([ { 'id': w.id, 'name': w.name, 'steps': w.steps } for w in defs ])

@workflows_bp.route('', methods=['POST'])
@jwt_required()
def create_definition():
    claims = get_jwt()
    if 'Administrator' not in claims.get('roles', []):
        return jsonify(msg='Forbidden'), 403
    data = request.get_json()
    w = WorkflowDefinition(name=data['name'], steps=data['steps'])
    db.session.add(w); db.session.commit()
    return jsonify(id=w.id), 201

@workflows_bp.route('/<int:wfid>', methods=['PUT'])
@jwt_required()
def update_definition(wfid):
    claims = get_jwt()
    if 'Administrator' not in claims.get('roles', []):
        return jsonify(msg='Forbidden'), 403
    data = request.get_json()
    w = WorkflowDefinition.query.get_or_404(wfid)
    w.name = data.get('name', w.name)
    w.steps = data.get('steps', w.steps)
    db.session.commit()
    return jsonify(msg='Updated'), 200

@workflows_bp.route('/<int:wfid>', methods=['DELETE'])
@jwt_required()
def delete_definition(wfid):
    claims = get_jwt()
    if 'Administrator' not in claims.get('roles', []):
        return jsonify(msg='Forbidden'), 403
    w = WorkflowDefinition.query.get_or_404(wfid)
    db.session.delete(w); db.session.commit()
    return jsonify(msg='Deleted'), 200

# GET /api/workflows/<wfid>
@workflows_bp.route('/<int:wfid>', methods=['GET'])
@jwt_required()
def get_definition(wfid):
    w = WorkflowDefinition.query.get_or_404(wfid)
    return jsonify({
        'id':    w.id,
        'name':  w.name,
        'steps': w.steps
    }), 200

# Start a workflow instance on an entity
@workflows_bp.route('/<int:wfid>/instances', methods=['POST'])
@jwt_required()
def start_instance(wfid):
    data = request.get_json()
    uid  = get_jwt_identity()
    # look for an existing instance for this user+workflow+entity
    inst = WorkflowInstance.query.filter_by(
      workflow_id = wfid,
      entity_type = data['entity_type'],
      entity_id   = data['entity_id'],
      user_id     = uid
    ).first()
    if not inst:
        # create a new one
        wdef = WorkflowDefinition.query.get_or_404(wfid)
        inst = WorkflowInstance(
          workflow_id  = wfid,
          entity_type  = data['entity_type'],
          entity_id    = data['entity_id'],
          user_id      = uid,
          current_step = 0,
          state        = wdef.steps[0]['name']
        )
        db.session.add(inst)
        db.session.commit()

    return jsonify(id=inst.id), 200

@workflows_bp.route('/<int:wfid>/instances', methods=['GET'])
@jwt_required()
def list_instances_for_definition(wfid):
    # only admins should see all instances
    claims = get_jwt()
    if 'Administrator' not in claims.get('roles', []) and \
       'Super Administrator' not in claims.get('roles', []):
        return jsonify(msg='Forbidden'), 403

    # fetch all instances for this workflow
    insts = WorkflowInstance.query.filter_by(workflow_id=wfid).all()
    results = []
    for inst in insts:
        results.append({
            'instance_id':   inst.id,
            'user_id':       inst.user_id,
            'current_step':  inst.current_step,
            'state':         inst.state,
            'created_at':    inst.logs[0]['at'] if inst.logs else None
        })
    return jsonify(instances=results), 200


@workflows_bp.route('/instances/tasks', methods=['GET'])
@jwt_required()
def list_my_tasks():
    uid   = get_jwt_identity()
    roles = get_jwt().get('roles', [])

    tasks = []
    # Fetch all workflow templates
    all_defs = WorkflowDefinition.query.all()

    for wdef in all_defs:
        wfid = wdef.id

        # See if this user already has an instance for this workflow
        inst = WorkflowInstance.query.filter_by(
            workflow_id = wfid,
            entity_type = 'workflow',
            entity_id   = 0,
            user_id     = uid
        ).first()

        # Determine if this user should have an instance at all
        # either because they’re the owner (starter), or appear in any step’s assign lists:
        any_assigned = any(
            uid in s.get('assign_users', []) or
            any(r in roles for r in s.get('assign_roles', []))
            for s in wdef.steps
        )

        # If they should but don’t yet have one, create it
        if any_assigned and not inst:
            inst = WorkflowInstance(
                workflow_id  = wfid,
                entity_type  = 'workflow',
                entity_id    = 0,
                user_id      = uid,
                current_step = 0,
                state        = wdef.steps[0]['name']
            )
            db.session.add(inst)
            db.session.commit()

        # If they own an instance (or we just created one), show it
        if inst:
            tasks.append({
                'workflow_id':    wfid,
                'instance_id':    inst.id,
                'workflow_name':  wdef.name,
                'step':           inst.state,
                'current_step':   inst.current_step,
                'entity_type':    inst.entity_type,
                'entity_id':      inst.entity_id
            })

    return jsonify(tasks), 200

@workflows_bp.route('/instances/<int:iid>', methods=['GET'])
@jwt_required()
def get_instance(iid):
    inst  = WorkflowInstance.query.get_or_404(iid)
    uid   = get_jwt_identity()
    roles = get_jwt().get('roles', [])

    # Authorization: allow the starter, any assigned user/role, or admins
    wdef  = WorkflowDefinition.query.get(inst.workflow_id)
    step  = wdef.steps[inst.current_step]
    is_owner          = (inst.user_id == uid)
    is_assigned_user  = uid in step.get('assign_users', [])
    is_assigned_role  = any(r in roles for r in step.get('assign_roles', []))
    is_admin          = any(r in ['Administrator','Super Administrator'] for r in roles)
    any_step_assigned = any(
       uid in s.get('assign_users', []) or 
       any(r in roles for r in s.get('assign_roles', []))
       for s in wdef.steps
    )
    if not (is_owner or is_assigned_user or is_assigned_role or is_admin or any_step_assigned):
        return jsonify(msg='Forbidden'), 403

    return jsonify({
        'id':            inst.id,
        'workflow_name': wdef.name,
        'steps':         wdef.steps,
        'current_step':  inst.current_step,
        'state':         inst.state,
        'logs':          inst.logs,
        'entity_type':   inst.entity_type,
        'entity_id':     inst.entity_id
    }), 200

# Transition a task to next state
@workflows_bp.route('/instances/<int:iid>/transition', methods=['POST'])
@jwt_required()
def transition(iid):
    data   = request.get_json()  # e.g. { comment: 'Looks good', approve: true }
    inst   = WorkflowInstance.query.get_or_404(iid)
    uid    = get_jwt_identity()
    claims = get_jwt()
    roles  = claims.get('roles', [])

    wdef = WorkflowDefinition.query.get(inst.workflow_id)
    step = wdef.steps[inst.current_step]
    # check permission:
    if uid not in step.get('assign_users', []) and not any(r in roles for r in step.get('assign_roles', [])):
      return jsonify(msg='Forbidden'), 403

    # append log
    new_logs = inst.logs or []
    new_logs.append({
      'by': uid,
      'step': inst.state,
      'at': datetime.utcnow().isoformat(),
      'comment': data.get('comment',''),
      'action': data.get('approve') and 'approved' or 'rejected'
    })
    inst.logs = new_logs

    # advance or finish
    if data.get('approve') and inst.current_step +1 < len(wdef.steps):
        inst.current_step += 1
        inst.state = wdef.steps[inst.current_step]['name']
        # send notifications to next assignees (similar to start_instance)
    else:
        inst.state = data.get('approve') and 'Completed' or 'Rejected'

    db.session.commit()
    return jsonify(msg='Transitioned', new_state=inst.state), 200
