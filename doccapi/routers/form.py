import logging
from typing import List, Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from doccapi.security import get_current_user
from doccapi.models.user import User
from doccapi.models.form import Form, FormEntry
from doccapi.database import (
    database,
    formdefinition_table,
    formfield_table,
    formentry_table,
    workflowdefinition_table,
    workflowinstance_table
)


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


@router.get("/{fid}", response_model=Form, status_code=200)
async def get_form(fid: int, current_user: Annotated[User, Depends(get_current_user)]):
    q = formdefinition_table.select().where(formdefinition_table.c.id == fid)
    f = await database.fetch_one(q)
    
    if not f:
        raise HTTPException(status_code=404, detail="Form not found")

    user_roles = current_user.roles if current_user.roles else []
    is_admin = "Super Administrator" in user_roles or "Administrator" in user_roles
    
    if not is_admin:
        has_entry_query = formentry_table.select().where(
            (formentry_table.c.form_id == fid) & 
            (formentry_table.c.user_id == current_user.id)
        )
        has_entry = await database.fetch_one(has_entry_query) is not None

        assigned = False
        workflow_instances_query = workflowinstance_table.select()
        
        instances = await database.fetch_all(workflow_instances_query)
        
        for inst in instances:
            wdef_query = workflowdefinition_table.select().where(
                workflowdefinition_table.c.id == inst.workflow_id
            )
            wdef = await database.fetch_one(wdef_query)
            
            if wdef and wdef.steps:
                for step in wdef.steps:
                    if (step.get("form_id") == fid and 
                        (current_user.id in step.get("assign_users", []) or
                         any(r in user_roles for r in step.get("assign_roles", [])))):
                        assigned = True
                        break
            if assigned:
                break

        if not (has_entry or assigned):
            raise HTTPException(status_code=403, detail="Forbidden")
    
    fields_query = formfield_table.select().where(
        formfield_table.c.form_id == fid
    ).order_by(formfield_table.c.order)
    fields = await database.fetch_all(fields_query)
    
    return {
        "id": f.id,
        "name": f.name,
        "description": f.description,
        "created_by": f.created_by,
        "fields": [
            {
                "id": field.id,
                "form_id": field.form_id,
                "name": field.name,
                "label": field.label,
                "field_type": field.field_type,
                "required": field.required,
                "options": field.options,
                "order": field.order
            }
            for field in fields
        ]
    }


@router.post("/", status_code=201)
async def create_form(form: Form, current_user: Annotated[User, Depends(require_roles(["Super Administrator", "Administrator"]))]):
    q = formdefinition_table.select().where(
        formdefinition_table.c.name == form.name
    )
    existing_form = await database.fetch_one(q)
    if existing_form:
        raise HTTPException(status_code=400, detail="Form with this name already exists")
    query = formdefinition_table.insert().values(
        name=form.name,
        description=form.description,
        created_by=current_user.id
    )
    form_id = await database.execute(query)
    
    if hasattr(form, 'fields') and form.fields:
        for f in form.fields:
            query_field = formfield_table.insert().values(
                form_id=form_id,
                name=f.name,
                label=f.label if hasattr(f, 'label') else f.name,
                field_type=f.field_type,
                required=f.required,
                options=f.options,
                order=f.order if hasattr(f, 'order') else 0
            )
            await database.execute(query_field)
    
    return {"message": "Form created successfully", "form_id": form_id}


@router.put("/{fid}", status_code=200)
async def update_form(fid: int, form: Form, current_user: Annotated[User, Depends(require_roles(["Super Administrator", "Administrator"]))]):
    check_query = formdefinition_table.select().where(formdefinition_table.c.id == fid)
    existing_form = await database.fetch_one(check_query)
    if not existing_form:
        raise HTTPException(status_code=404, detail="Form not found")
    query = formdefinition_table.update().where(formdefinition_table.c.id == fid).values(
        name=form.name,
        description=form.description
    )
    await database.execute(query)
    if hasattr(form, 'fields') and form.fields:
        existing_fields_query = formfield_table.select().where(formfield_table.c.form_id == fid)
        existing_fields = await database.fetch_all(existing_fields_query)

        if existing_fields:
            for f in form.fields:
                if f.id is not None:
                    query_field = formfield_table.update().where(
                        formfield_table.c.id == f.id,
                        formfield_table.c.form_id == fid
                    ).values(
                        name=f.name,
                        label=f.label if hasattr(f, 'label') else f.name,
                        field_type=f.field_type,
                        required=f.required,
                        options=f.options,
                        order=f.order
                    )
                    await database.execute(query_field)
        else:
            for f in form.fields:
                insert_field = formfield_table.insert().values(
                    form_id=fid,
                    name=f.name,
                    label=f.label if hasattr(f, 'label') else f.name,
                    field_type=f.field_type,
                    required=f.required,
                    options=f.options,
                    order=f.order if hasattr(f, 'order') else 0
                )
                await database.execute(insert_field)
    return {"message": "Form updated successfully", "form_id": fid}


@router.get("/{fid}/entries/mine", status_code=200)
async def get_my_entries(fid: int, current_user: Annotated[User, Depends(get_current_user)]):
    if 'Administrator' in current_user.roles or 'Super Administrator' in current_user.roles:
        query = formentry_table.select().where(formentry_table.c.id == fid)
    else:
        query = formentry_table.select().where(formentry_table.c.id == fid, formentry_table.c.user_id == current_user.id)
    entries = await database.fetch_all(query)
    
    if not entries:
        raise HTTPException(status_code=404, detail="No entries found for this form")
    
    return [FormEntry(id=entry.id, form_id=entry.form_id, user_id=entry.user_id, data=entry.data, status=entry.status) for entry in entries]


@router.get("/{fid}/entries", status_code=200)
async def get_all_entries(fid: int, current_user: Annotated[User, Depends(require_roles(["Super Administrator", "Administrator"]))]):
    query = formentry_table.select().where(formentry_table.c.form_id == fid)
    entries =  await database.fetch_all(query)
    return [FormEntry(id=entry.id, form_id=entry.form_id, user_id=entry.user_id, data=entry.data, status=entry.status) for entry in entries]

# e.g. /forms/1/entries?workflow_instance_id=123
@router.post("/{fid}/entries", status_code=201)
async def submit_entry(
    fid: int, 
    FormEntry: FormEntry,
    current_user: Annotated[User, Depends(get_current_user)],
    workflow_instance_id: Optional[int] = None
):
    query = formentry_table.insert().values(
        form_id=fid,
        user_id=current_user.id,
        data=FormEntry.data,
        status=FormEntry.status
    )
    entry_id = await database.execute(query)

    if workflow_instance_id:
        inst_query = workflowinstance_table.select().where(
            workflowinstance_table.c.id == workflow_instance_id
        )
        inst = await database.fetch_one(inst_query)
        
        if not inst:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        wdef_query = workflowdefinition_table.select().where(
            workflowdefinition_table.c.id == inst.workflow_id
        )
        wdef = await database.fetch_one(wdef_query)
        
        if wdef and wdef.steps and inst.current_step < len(wdef.steps):
            current_step = wdef.steps[inst.current_step]
            
            if current_step.get("form_id") == fid:
                is_assigned = (
                    current_user.id in current_step.get("assign_users", []) or
                    any(r in current_user.roles for r in current_step.get("assign_roles", []))
                )
                
                if is_assigned:
                    update_query = workflowinstance_table.update().where(
                        workflowinstance_table.c.id == workflow_instance_id
                    ).values(
                        user_id=current_user.id,
                        entity_id=entry_id,
                        entity_type="form_entry"
                    )
                    await database.execute(update_query)
                else:
                    raise HTTPException(status_code=403, detail="Not assigned to this workflow step")
            else:
                raise HTTPException(status_code=400, detail="Form does not match current workflow step")

    return {
        "message": "Form entry submitted successfully", 
        "entity_id": entry_id,
        "workflow_instance_id": workflow_instance_id
    }


@router.put("/entries/{eid}", status_code=200)
async def update_entry(eid: int, FormEntry: FormEntry, current_user: Annotated[User, Depends(get_current_user)]):
    #Update form entry
    query = formentry_table.update().where(
        formentry_table.c.id == eid,
        formentry_table.c.user_id == current_user.id
    ).values(
        data=FormEntry.data,
        status=FormEntry.status
    )
    
    result = await database.execute(query)
    
    if result == 0:
        raise HTTPException(status_code=404, detail="Form entry not found or not owned by user")
    
    return {"message": "Entry updated", "entry_id": eid}


@router.delete("/{fid}", status_code=200)
async def delete_form(fid: int, current_user: Annotated[User, Depends(require_roles(["Super Administrator", "Administrator"]))]):
    query = formentry_table.select().where(formentry_table.c.form_id == fid)
    entries = await database.fetch_all(query)
    entry_count = len(entries)
    
    if entry_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete form. It has {entry_count} associated entries."
        )
    #Check Fields
    delete_fields = formfield_table.delete().where(formfield_table.c.form_id == fid)
    await database.execute(delete_fields)
    
    #Delete Form
    delete_form = formdefinition_table.delete().where(formdefinition_table.c.id == fid)
    result = await database.execute(delete_form)
    
    if result == 0:
        raise HTTPException(status_code=404, detail="Form not found")
    
    return {"message": "Form deleted successfully", "form_id": fid}


@router.delete("/entries/{eid}", status_code=200)
async def delete_entry(eid: int, current_user: Annotated[User, Depends(get_current_user)]):
    query = formentry_table.select().where(
        formentry_table == eid
    )
    entry = await database.execute(query)
    if entry.user_id != current_user.id and not any(
        r in ["Super Administrator", "Administrator"] for r in current_user.roles
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    delete_entry = formentry_table.delete().where(entry.id == eid)
    return {"message": "Entry deleted", "entry_id": eid}


@router.get("/", status_code=200)
async def list_forms(
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = 1,
    per_page: int = 10
):
    offset = (page - 1) * per_page
    
    user_roles = current_user.roles if current_user.roles else []
    is_admin = any(role in ["Super Administrator", "Administrator"] for role in user_roles)
    
    if is_admin:
        count_query = "SELECT COUNT(*) FROM form_definition"
        total_count = await database.fetch_val(count_query)
        
        query = """
            SELECT 
                fd.id,
                fd.name,
                fd.description,
                fe.id as entry_id
            FROM form_definition fd
            LEFT JOIN form_entry fe ON fd.id = fe.form_id
            ORDER BY fd.created_at DESC
            LIMIT :limit OFFSET :offset
        """

        forms = await database.fetch_all(query, {
            "limit": per_page, 
            "offset": offset
        })
        
    else:
        uid = current_user.id
        
        # 1) 用户提交过的表单
        entry_query = """
            SELECT DISTINCT form_id FROM form_entry WHERE user_id = :user_id
        """
        entry_rows = await database.fetch_all(entry_query, {"user_id": uid})
        entry_ids = [row.form_id for row in entry_rows]
        
        # 2) 工作流中分配给用户的表单
        assigned_ids = []
        workflow_query = "SELECT * FROM workflow_definition"
        workflows = await database.fetch_all(workflow_query)
        
        for workflow in workflows:
            steps = workflow.steps if hasattr(workflow, 'steps') else []
            for step in steps:
                assign_users = step.get("assign_users", []) if isinstance(step, dict) else []
                assign_roles = step.get("assign_roles", []) if isinstance(step, dict) else []
                
                if (uid in assign_users or 
                    any(role in user_roles for role in assign_roles)):
                    form_id = step.get("form_id") if isinstance(step, dict) else None
                    if isinstance(form_id, int):
                        assigned_ids.append(form_id)
        
        allowed_ids = list(set(entry_ids) | set(assigned_ids))
        
        if not allowed_ids:
            return {
                "forms": [],
                "page": page,
                "per_page": per_page,
                "total": 0,
                "total_pages": 0
            }
        
        placeholders = ",".join([f":id_{i}" for i in range(len(allowed_ids))])
        count_query = f"SELECT COUNT(*) FROM form_definition WHERE id IN ({placeholders})"
        count_params = {f"id_{i}": allowed_ids[i] for i in range(len(allowed_ids))}
        total_count = await database.fetch_val(count_query, count_params)
        
        # 修改：使用 LEFT JOIN 获取表单和条目ID
        forms_query = f"""
            SELECT 
                fd.id,
                fd.name,
                fd.description,
                fe.id as entry_id
            FROM form_definition fd
            LEFT JOIN form_entry fe ON fd.id = fe.form_id AND fe.user_id = :user_id
            WHERE fd.id IN ({placeholders}) 
            ORDER BY fd.created_at DESC 
            LIMIT :limit OFFSET :offset
        """
        forms_params = {**count_params, "user_id": uid, "limit": per_page, "offset": offset}
        forms = await database.fetch_all(forms_query, forms_params)
    
    # 计算总页数
    total_pages = (total_count + per_page - 1) // per_page
    
    return {
        "forms": [
            {
                "id": form.id,
                "name": form.name,
                "description": form.description,
                "entity_id": form.entry_id  # 添加条目ID，可能为None
            }
            for form in forms
        ],
        "page": page,
        "per_page": per_page,
        "total": total_count,
        "total_pages": total_pages
    }
