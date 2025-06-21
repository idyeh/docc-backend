import logging
from typing import List, Annotated
from datetime import datetime

import sqlalchemy
from fastapi import APIRouter, Depends, HTTPException
from doccapi.security import get_current_user
from doccapi.database import database, workflowdefinition_table, workflowinstance_table, formentry_table
from doccapi.models.user import User
from doccapi.models.workflow import Workflow, Workflowinstance, Log

logger = logging.getLogger(__name__)
router = APIRouter()


def require_roles(allowed_roles: List[str]):
    async def check_roles(current_user: Annotated[User, Depends(get_current_user)]):
        user_roles = current_user.roles if current_user.roles else []
        logger.debug(f"Current user roles: {user_roles}")

        if not any(role in allowed_roles for role in user_roles):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions",
            )
        
        return current_user
    return check_roles


@router.get("", response_model=List[Workflow])
async def list_definitions(current_user: Annotated[User, Depends(require_roles(["Administrator", "Super Administrator"]))]):
    if "Administrator" and "Super Administrator" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    query = workflowdefinition_table.select()
    defs = await database.fetch_all(query)
    
    workflows = []
    for def_record in defs:
        workflow = Workflow(
            id=def_record.id,
            name=def_record.name,
            steps=def_record.steps
        )
        workflows.append(workflow)
    
    return workflows


@router.post("")
async def create_definition(workflow: Workflow, current_user: Annotated[User, Depends(require_roles(["Administrator", "Super Administrator"]))]):
    if "Administrator" and "Super Administrator" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    query = workflowdefinition_table.insert().values(
        name=workflow.name,
        steps=workflow.steps
    )
    w = await database.execute(query)
    
    return {"message": "Workflow definition created successfully"}


@router.put("/{wfid}", status_code=200)
async def update_definition(wfid: int, workflow: Workflow, current_user: Annotated[User, Depends(require_roles(["Administrator", "Super Administrator"]))]):
    if "Administrator" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    query = workflowdefinition_table.update().where(workflowdefinition_table.c.id == wfid).values(
        name=workflow.name,
        steps=workflow.steps
    )
    await database.execute(query)
    
    return {"message": "Updated"}


@router.get("/{wfid}", response_model=Workflow)
async def get_definition(wfid: int, current_user: Annotated[User, Depends(get_current_user)]):    
    query = workflowdefinition_table.select().where(workflowdefinition_table.c.id == wfid)
    def_record = await database.fetch_one(query)
    
    if not def_record:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    
    workflow = Workflow(
        id=def_record.id,
        name=def_record.name,
        steps=def_record.steps
    )
    
    return workflow


#Start a workflow instance on an entity
@router.post("/{wfid}/instances", status_code=201)
async def start_instance(wfid: int, wfi: Workflowinstance, current_user: Annotated[User, Depends((get_current_user))]):
    query = workflowinstance_table.select().where(
        (workflowinstance_table.c.workflow_id == wfid) and
        (workflowinstance_table.c.entity_type == wfi.entity_type) and
        (workflowinstance_table.c.entity_id == wfi.entity_id) and
        (workflowinstance_table.c.user_id == current_user.id)
    )
    inst = await database.fetch_one(query)
    if not inst:
        wdef = workflowdefinition_table.select().where(workflowdefinition_table.c.id == wfid)
        inst = Workflowinstance(
            workflow_id = wfid,
            user_id = current_user.id,
            entity_type = wfi.entity_type,
            entity_id = wfi.entity_id,
            current_step = 0,
            state = wdef.steps[0]["name"]
        )

    return {"id": inst.id}


@router.get("/{iid}/instances/history", status_code=200)
async def get_history_for_instance(iid: int, current_user: Annotated[User, Depends(get_current_user)]):
    if "Administrator" and "Super Administrator" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    query = workflowinstance_table.select().where(workflowinstance_table.c.id == iid)
    inst = await database.fetch_one(query)
    
    if inst:
        if not inst.logs:
            return []
        
        logs = []
        for log in inst.logs:
            logs.append({
                "by": log['by'],
                "step": log['step'],
                "at": log['at'],
                "comment": log['comment'],
                "action": log['action'],
                "entity_type": log['entity_type'] if 'entity_type' in log else 'example_entry',
                "entity_id": log['entity_id'] if 'entity_id' in log else '0'
            })
        return logs

    return logs


@router.get("/{wfid}/instances")
async def list_instances_for_definition(wfid: int, current_user: Annotated[User, Depends(require_roles(["Administrator", "Super Administrator"]))]):
    if "Administrator" and "Super Administrator" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    query = sqlalchemy.select(
        workflowinstance_table.c.id,
        workflowinstance_table.c.user_id,
        workflowinstance_table.c.workflow_id,
        workflowinstance_table.c.current_step,
        workflowinstance_table.c.state,
        workflowinstance_table.c.entity_id,
        workflowinstance_table.c.entity_type,
        workflowinstance_table.c.logs,
        formentry_table.c.form_id
    ).select_from(
        workflowinstance_table.outerjoin(
            formentry_table,
            (workflowinstance_table.c.entity_id == formentry_table.c.id) &
            (workflowinstance_table.c.entity_type == 'form_entry')
        )
    ).where(workflowinstance_table.c.workflow_id == wfid)
    instances = await database.fetch_all(query)

    results = []
    for inst in instances:
        results.append(Workflowinstance(
            id = inst.id,
            user_id = inst.user_id,
            workflow_id= inst.workflow_id,
            current_step = inst.current_step,
            state = inst.state,
            form_id = inst.form_id,
            entity_id = inst.entity_id,
            entity_type= inst.entity_type,
            logs = inst.logs if inst.logs else None
        ))
    
    return results


@router.get("/instances/tasks")
async def list_my_tasks(current_user: Annotated[User, Depends(get_current_user)]):
    tasks = []
    query = workflowdefinition_table.select()
    all_defs = await database.fetch_all(query)

    for wdef in all_defs:
        wfid = wdef.id

        any_assigned = any(
            current_user.id in s.get('assign_users', []) or
            any(r in current_user.roles for r in s.get('assign_roles', []))
            for s in wdef.steps
        )

        if not any_assigned:
            continue
        
        user_first_step = None
        for i, s in enumerate(wdef.steps):
            assigned = (
                current_user.id in s.get('assign_users', []) or
                any(r in current_user.roles for r in s.get('assign_roles', []))
            )
            if assigned:
                user_first_step = i
                break

        user_instances_query = workflowinstance_table.select().where(
            (workflowinstance_table.c.workflow_id == wfid) &
            (workflowinstance_table.c.user_id == current_user.id)
        )
        user_instances = await database.fetch_all(user_instances_query)

        all_instances_query = workflowinstance_table.select().where(
            workflowinstance_table.c.workflow_id == wfid
        )
        all_instances = await database.fetch_all(all_instances_query)

        participating_instances = []
        for inst in all_instances:
            if inst.current_step < len(wdef.steps):
                current_step = wdef.steps[inst.current_step]
                is_assigned_to_current_step = (
                    current_user.id in current_step.get('assign_users', []) or
                    any(r in current_user.roles for r in current_step.get('assign_roles', []))
                )
                
                if is_assigned_to_current_step:
                    participating_instances.append(inst)

        all_relevant_instances = user_instances + [
            inst for inst in participating_instances 
            if inst.id not in [ui.id for ui in user_instances]
        ]

        if not all_relevant_instances and user_first_step == 0:
            inst = Workflowinstance(
                workflow_id=wfid,
                user_id=current_user.id,
                entity_type="workflow",
                entity_id=0,
                current_step=0,
                state=wdef.steps[0]['name']
            )
            insert_query = workflowinstance_table.insert().values(
                workflow_id=inst.workflow_id,
                user_id=inst.user_id,
                entity_type=inst.entity_type,
                entity_id=inst.entity_id,
                current_step=inst.current_step,
                state=inst.state
            )
            inst.id = await database.execute(insert_query)
            all_relevant_instances = [inst]

        for inst in all_relevant_instances:
            if inst.current_step < len(wdef.steps) and inst.state!= 'Completed':
                current_step = wdef.steps[inst.current_step]

                is_assigned_to_current_step = (
                    current_user.id in current_step.get('assign_users', []) or
                    any(r in current_user.roles for r in current_step.get('assign_roles', []))
                )
                if is_assigned_to_current_step:
                    tasks.append(Workflowinstance(
                        id=inst.id,
                        workflow_id=wfid,
                        workflow_name=wdef.name,
                        form_id=current_step.get('form_id'),
                        user_id=inst.user_id,
                        entity_type=inst.entity_type,
                        entity_id=inst.entity_id,
                        current_step=inst.current_step,
                        state=inst.state,
                        logs=inst.logs if inst.logs else []
                    ))

    return tasks

@router.get("/instances/{iid}", response_model=Workflowinstance)
async def get_instance(iid: int, current_user: Annotated[User, Depends(get_current_user)]):
    query = workflowinstance_table.select().where(workflowinstance_table.c.id == iid)
    inst = await database.fetch_one(query)
    
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow instance not found")

    # Authorization: allow the starter, any assigned user/role, or admins
    q = workflowdefinition_table.select().where(workflowdefinition_table.c.id == inst.workflow_id)
    wdef = await database.fetch_one(q)
    
    if not wdef:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    
    step = wdef.steps[inst.current_step]

    is_owner          = (inst.user_id == current_user.id)
    is_assigned_user  = current_user.id in step.get('assign_users', [])
    is_assigned_role  = any(r in current_user.roles for r in step.get('assign_roles', []))
    is_admin          = any(r in ['Administrator','Super Administrator'] for r in current_user.roles)
    any_step_assigned = any(
       current_user.id in s.get('assign_users', []) or 
       any(r in current_user.roles for r in s.get('assign_roles', []))
       for s in wdef.steps
    )
    if not (is_owner or is_assigned_user or is_assigned_role or is_admin or any_step_assigned):
        raise HTTPException(status_code=403, detail="Forbidden")

    return Workflowinstance(
        id=inst.id,
        workflow_id=inst.workflow_id,
        user_id=inst.user_id,
        entity_type=inst.entity_type,
        entity_id=inst.entity_id,
        current_step=inst.current_step,
        state=inst.state,
        logs=inst.logs if inst.logs else []
    )

@router.delete("/instances/{iid}", status_code=204)
async def delete_instance(iid: int, current_user: Annotated[User, Depends(require_roles(["Administrator", "Super Administrator"]))]):
    if "Administrator" and "Super Administrator" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    query = workflowinstance_table.select().where(workflowinstance_table.c.id == iid)
    inst = await database.fetch_one(query)
    
    if not inst:
        raise HTTPException(status_code=404, detail="instance not found")

    delete_query = workflowinstance_table.delete().where(workflowinstance_table.c.id == iid)
    await database.execute(delete_query)

    return {"message": "instance deleted successfully"}

@router.put("/instances/{iid}/transition", response_model=Workflowinstance)
async def transition_instance(iid: int, log: Log, current_user: Annotated[User, Depends(get_current_user)]):
    query = workflowinstance_table.select().where(workflowinstance_table.c.id == iid)
    inst = await database.fetch_one(query)
    
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow instance not found")

    wdef_query = workflowdefinition_table.select().where(workflowdefinition_table.c.id == inst.workflow_id)
    wdef = await database.fetch_one(wdef_query)
    
    if not wdef:
        raise HTTPException(status_code=404, detail="Workflow definition not found")

    if inst.current_step >= len(wdef.steps):
        raise HTTPException(status_code=400, detail="Workflow already completed")

    step = wdef.steps[inst.current_step]

    is_assigned_user = current_user.id in step.get('assign_users', [])
    is_assigned_role = any(r in current_user.roles for r in step.get('assign_roles', []))
    is_admin = any(r in ['Administrator', 'Super Administrator'] for r in current_user.roles)

    if not (is_assigned_user or is_assigned_role or is_admin):
        raise HTTPException(status_code=403, detail="Forbidden: You are not authorized to transition this step")

    current_logs = inst.logs if inst.logs else []
    new_log_entry = {
        'by': current_user.id,
        "submitted_user": inst.user_id,
        'step': inst.state,
        'at': datetime.now().isoformat(),
        'comment': log.comment,
        'action': log.action,  # 'approved' wor 'rejected'
        'entity_type': inst.entity_type,
        'entity_id': inst.entity_id
    }
    current_logs.append(new_log_entry)

    new_step = inst.current_step
    new_state = inst.state

    if log.action == 'approved':
        if inst.current_step + 1 < len(wdef.steps):
            new_step = inst.current_step + 1
            new_state = wdef.steps[new_step]['name']
        else:
            new_state = 'Completed'
    else:
        new_state = 'Rejected'

    update_query = workflowinstance_table.update().where(
        workflowinstance_table.c.id == iid
    ).values(
        current_step=new_step,
        state=new_state,
        logs=current_logs,
        entity_type='workflow'
    )
    
    await database.execute(update_query)


    return Workflowinstance(
        id=inst.id,
        workflow_id=inst.workflow_id,
        entity_type=inst.entity_type,
        entity_id=inst.entity_id,
        current_step=new_step,
        state=new_state,
        logs=current_logs
    )
