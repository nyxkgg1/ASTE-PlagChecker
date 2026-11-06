from pydantic import BaseModel, EmailStr
from app.core.encryption import encrypt_json

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    full_name: str
    roles: list[str]