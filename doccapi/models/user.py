from pydantic import BaseModel

class Role(BaseModel):
    id: int | None = None
    name: str


class User(BaseModel):
    id: int | None = None
    email: str
    username: str | None = None
    password_hash: str | None = None
    password: str
    roles: list = []
    confirmed: bool = False


class UserIn(User):
    password: str

class UserUpdateIn(BaseModel):
    username: str | None = None
    password: str | None = None
    roles: list[str] | None = None
