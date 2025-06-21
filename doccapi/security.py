import datetime
import logging
from typing import Annotated, Literal

import sqlalchemy
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from doccapi.database import database, user_table, user_role_table, role_table
from doccapi.models.user import User
logging.getLogger('passlib').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

SECRET_KEY = "8cbd121cf001328d4e01564e8a9cd40d83e1ae233f3062e28dec5f0a04b506f9"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/token")
pwd_context = CryptContext(schemes=["bcrypt"])


def create_unauthorized_exception(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def access_token_expire_minutes() -> int:
    return 60


def confirm_token_expire_minutes() -> int:
    return 1440


def create_access_token(email: str):
    logger.debug("Creating access token", extra={"email": email})
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=access_token_expire_minutes()
    )
    jwt_data = {"sub": email, "exp": expire, "type": "access"}
    encoded_jwt = jwt.encode(jwt_data, key=SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_confirmation_token(email: str):
    logger.debug("Creating confirmation token", extra={"email": email})
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=confirm_token_expire_minutes()
    )
    jwt_data = {"sub": email, "exp": expire, "type": "confirmation"}
    encoded_jwt = jwt.encode(jwt_data, key=SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_subject_for_token_type(
    token: str, type: Literal["access", "confirmation"]
) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError as e:
        raise create_unauthorized_exception("Token has expired") from e
    except JWTError as e:
        raise create_unauthorized_exception("Invalid token") from e

    email = payload.get("sub")
    if email is None:
        raise create_unauthorized_exception("Token is missing 'sub' field")

    token_type = payload.get("type")
    if token_type is None or token_type != type:
        raise create_unauthorized_exception(
            f"Token has incorrect type, expected '{type}'"
        )

    return email


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


async def get_user(email: str):
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
        .where(user_table.c.email == email)
        .group_by(
            user_table.c.id,
            user_table.c.email,
            user_table.c.username,
            user_table.c.password,
            user_table.c.password_hash,
            user_table.c.confirmed
        )
    )
    result = await database.fetch_one(query)
    if result:
        role_names = result.roles.split(',') if result.roles else []
        roles = [role_name for role_name in role_names]

        return User(
            id=result.id,
            email=result.email,
            username=result.username,
            password=result.password,
            password_hash=result.password_hash,
            confirmed=result.confirmed,
            roles=roles
        )

    return None

async def get_user_by_id(user_id: int):
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
        .where(user_table.c.id == user_id)
        .group_by(
            user_table.c.id,
            user_table.c.email,
            user_table.c.username,
            user_table.c.password,
            user_table.c.password_hash,
            user_table.c.confirmed
        )
    )
    result = await database.fetch_one(query)
    if result:
        role_names = result.roles.split(',') if result.roles else []
        roles = [role_name for role_name in role_names]

        return User(
            id=result.id,
            email=result.email,
            username=result.username,
            password=result.password,
            password_hash=result.password_hash,
            confirmed=result.confirmed,
            roles=roles
        )

    return None

async def authenticate_user(email: str, password: str):
    logger.debug("Authenticating user", extra={"email": email})
    user = await get_user(email)
    if not user:
        raise create_unauthorized_exception("Invalid email or password")
    if not verify_password(password, user.password_hash):
        raise create_unauthorized_exception("Invalid email or password")
    if not user.confirmed:
        raise create_unauthorized_exception("User has not confirmed email")
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    email = get_subject_for_token_type(token, "access")
    user = await get_user(email=email)
    if user is None:
        raise create_unauthorized_exception("Could not find user for this token")
    return user
