import logging
from typing import List, Annotated

import sqlalchemy
from fastapi import APIRouter, HTTPException, Request, status, Depends
from doccapi.models.user import UserIn, User, UserUpdateIn
from doccapi.security import (
    authenticate_user,
    create_access_token,
    create_confirmation_token,
    get_password_hash,
    get_subject_for_token_type,
    get_user,
    get_user_by_id,
    get_current_user,
)
from doccapi.database import database, user_table, user_role_table, role_table

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


@router.get("", response_model=List[User], status_code=200)
async def list_users(current_user: Annotated[User, Depends(require_roles(['Administrator', 'Super Administrator']))]):
    query = (
        sqlalchemy.select(
            user_table.c.id,
            user_table.c.email,
            user_table.c.username,
            user_table.c.password,
            user_table.c.password_hash,
            user_table.c.confirmed,
            sqlalchemy.func.group_concat(role_table.c.name).label("roles"),
        )
        .select_from(
            user_table
            .join(user_role_table, user_table.c.id == user_role_table.c.user_id, isouter=True)
            .join(role_table, user_role_table.c.role_id == role_table.c.id, isouter=True)
        )
        .group_by(
            user_table.c.id,
            user_table.c.email,
            user_table.c.username,
            user_table.c.password,
            user_table.c.password_hash,
            user_table.c.confirmed
        )
        .order_by(user_table.c.username)
    )

    result = await database.fetch_all(query)
    processed_users = []
    if result:
        for user in result:
            user_dict = dict(user)
            if user_dict.get('roles'):
                user_dict['roles'] = user_dict['roles'].split(',')
            else:
                user_dict['roles'] = []
            processed_users.append(user_dict)
    return processed_users


@router.get("/get_user/{uid}", response_model=User, status_code=201)
async def get_specific_user(
    current_user: Annotated[User, Depends(require_roles(['Administrator', 'Super Administrator']))],
):
    return current_user


@router.get("/confirm/{token}")
async def confirm_email(token: str):
    email = get_subject_for_token_type(token, "confirmation")
    query = (
        user_table.update().where(user_table.c.email == email).values(confirmed=True)
    )

    logger.debug(query)

    await database.execute(query)
    return {"detail": "User confirmed"}


@router.post("/token", status_code=200)
async def login(user: UserIn):
    user = await authenticate_user(user.email, user.password)
    access_token = create_access_token(user.email)
    return {"access_token": access_token, "token_type": "bearer", **user.model_dump()}


@router.post("/register", status_code=201)
async def register(user: UserIn, request: Request):
    u = await get_user(user.email)
    logger.debug(f"User lookup result: {u}")
    if u is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with that email already exists",
        )
    hashed_password = get_password_hash(user.password)
    query = user_table.insert().values(
        email=user.email,
        username=user.username,
        password=user.password,
        password_hash=hashed_password,
    )

    logger.debug(query)

    await database.execute(query)
    return {
        "detail": "User created. Please confirm your email.",
        "confirmation_url": request.url_for(
            "confirm_email", token=create_confirmation_token(user.email)
        ),
    }


@router.put("/update_user/{uid}", status_code=200)
async def update_user(uid: int, current_user: Annotated[User, Depends(get_current_user)], user: UserUpdateIn):
    existing_user = await get_user_by_id(uid)
    is_self = (existing_user.id == current_user.id)
    is_admin = any(role in current_user.roles for role in ['Administrator', 'Super Administrator'])
    if not (is_self or is_admin):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update this user",
        )

    update_values = {}
    if user.username is not None:
        update_values['username'] = user.username
    if user.password is not None:
        update_values['password'] = user.password
        update_values['password_hash'] = get_password_hash(user.password)
    
    if update_values:
        query = (
            user_table.update()
            .where(user_table.c.id == uid)
            .values(**update_values)
        )
        logger.debug(query)
        result = await database.execute(query)
        
        if result == 0:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

    # only admin
    if is_admin and user.roles is not None:
        if not isinstance(user.roles, list) or not all(isinstance(r, str) for r in user.roles):
            raise HTTPException(
                status_code=400,
                detail="Invalid roles format"
            )
        
        # check if roles exist
        if user.roles:
            role_query = role_table.select().where(role_table.c.name.in_(user.roles))
            existing_roles = await database.fetch_all(role_query)
            existing_role_names = {role.name for role in existing_roles}
            missing_roles = set(user.roles) - existing_role_names
            
            if missing_roles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown roles: {', '.join(missing_roles)}"
                )
        
        delete_query = user_role_table.delete().where(user_role_table.c.user_id == uid)
        logger.debug(delete_query)
        await database.execute(delete_query)
        
        if user.roles:
            for role in existing_roles:
                insert_query = user_role_table.insert().values(
                    user_id=uid,
                    role_id=role.id
                )
                logger.debug(insert_query)
                await database.execute(insert_query)
    
    return {"user_roles": user.roles}


@router.delete("/delete_user/{uid}", status_code=204)
async def delete_user(
    current_user: Annotated[User, Depends(require_roles(['Super Administrator']))],
    uid: int
):
    query = user_table.delete().where(user_table.c.id == uid)

    logger.debug(query)

    result = await database.execute(query)
    if result == 0:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    return {"detail": "User deleted successfully", "user_id": uid}
