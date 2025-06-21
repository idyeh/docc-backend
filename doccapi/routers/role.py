from typing import List, Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException
from doccapi.models.user import User
from doccapi.models.role import Role
from doccapi.security import get_current_user
from doccapi.database import database, role_table
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

@router.get("", status_code=200)
async def list_roles():
    query = role_table.select().order_by(role_table.c.name)
    roles = await database.fetch_all(query)
    return roles


@router.get("/{role_id}", response_model=Role, status_code=200)
async def get_role(role_id: int, current_user: Annotated[User, Depends(require_roles(['Administrator', 'Super Administrator']))]):
    query = role_table.select().where(role_table.c.id == role_id)
    role = await database.fetch_one(query)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"message": "role created", "role_id": role}


@router.post("", status_code=201)
async def create_role(role: Role, current_user: Annotated[User, Depends(require_roles(['Administrator', 'Super Administrator']))]):
    q = role_table.select().where(role_table.c.name == role.name)
    existing_role = await database.fetch_one(q)
    if existing_role:
        raise HTTPException(status_code=400, detail="Role already exists")
    query = role_table.insert().values(name=role.name)
    role = await database.execute(query)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.put("/{role_id}", response_model=Role, status_code=200)
async def update_role(role_id: int, role: Role, current_user: Annotated[User, Depends(require_roles(['Administrator', 'Super Administrator']))]):
    query = role_table.update().where(role_table.c.id == role_id).values(name=role.name)
    result = await database.execute(query)
    return {**result, "id": role_id}


@router.delete("/{role_id}", status_code=204)
async def delete_role(role_id: int, current_user: Annotated[User, Depends(require_roles(['Administrator', 'Super Administrator']))]):
    query = role_table.delete().where(role_table.c.id == role_id)
    result = await database.execute(query)
    if result == 0:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"detail": "Role deleted successfully"}