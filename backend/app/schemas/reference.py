from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

from app.models.plagiarism import DocumentRequest
from app.api.dependencies import require_roles

class ReferenceDocumentResponse(BaseModel):
    id: str
    title: str
    document_type: str
    file_name: str
    file_size: int | None
    mime_type: str | None
    sha256_hash: str
    status: str
    current_version: int
    added_by: str | None
    approved_by: str | None
    created_at: str | None = None


class UpdateReferenceRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class CreateReferenceRequestPayload(BaseModel):
    request_type: str = Field(pattern="^(ADD|UPDATE|DELETE)$")
    title: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=2000)
    reference_document_id: Optional[str] = None


class ReferenceRequestResponse(BaseModel):
    id: str
    request_type: str
    requested_by: str
    reference_document_id: str | None
    scan_id: str | None = None
    title: str
    reason: str
    status: str
    reviewed_by: str | None
    reviewed_at: str | None
    rejection_reason: str | None
    admin_comments: str | None
    created_at: str
    pending_file_name: str | None = None

class ReviewReferenceRequestPayload(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    admin_comments: Optional[str] = Field(
        default=None,
        max_length=2000
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=2000
    )

class CreateReferenceAddRequestResponse(BaseModel):
    id: str
    request_type: str
    title: str
    reason: str
    status: str
    pending_file_name: str | None
    created_at: str


class ReviewReferenceRequestPayload(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    admin_comments: str | None = Field(default=None, max_length=2000)
    rejection_reason: str | None = Field(default=None, max_length=2000)

class ReferenceIndexResponse(BaseModel):
    reference_id: str
    title: str
    version: int
    status: str
    sentence_count: int
    embedding_count: int
