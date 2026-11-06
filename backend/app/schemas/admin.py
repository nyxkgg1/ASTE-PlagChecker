from pydantic import BaseModel, EmailStr, Field
from app.models.audit import AuditLog
from typing import Literal

class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8)
    role_name: str


class RoleAssignmentRequest(BaseModel):
    role_name: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    full_name: str
    status: str
    roles: list[str]

class ScanApprovalPayload(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    admin_comments: str | None = None


class PlagiarismExclusionsPayload(BaseModel):
    words: list[str] = Field(max_length=500)
    phrases: list[str] = Field(max_length=500)