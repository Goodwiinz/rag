"""Request and response schemas for the immutable project-skill catalog."""

from uuid import UUID

from pydantic import BaseModel, Field


class SkillDocumentRequest(BaseModel):
    document_text: str = Field(min_length=1, max_length=100_000)


class ApprovalRequest(BaseModel):
    self_approval_acknowledged: bool = False
    warning_acknowledged: bool = False
    audit_note: str | None = Field(default=None, max_length=4_000)


class RejectRequest(BaseModel):
    audit_note: str = Field(min_length=1, max_length=4_000)


class RollbackRequest(BaseModel):
    version_id: UUID


class ScanFindingResponse(BaseModel):
    code: str
    severity: str
    message: str
    line: int | None = None


class SkillVersionResponse(BaseModel):
    id: UUID
    version: int
    name: str
    description: str
    content_hash: str
    document_text: str
    scan_state: str
    scan_findings: list[ScanFindingResponse]


class SkillResponse(BaseModel):
    id: UUID
    name: str
    active_version_id: UUID | None
    is_archived: bool
    versions: list[SkillVersionResponse] = []


class ChangeRequestResponse(BaseModel):
    id: UUID
    action: str
    status: str
    proposed_version_id: UUID | None
    expected_active_version_id: UUID | None
    audit_note: str | None
    skill_id: UUID
    skill_name: str
    requester_id: UUID
    reviewer_id: UUID | None
    warning_acknowledged: bool
    created_at: str
    reviewed_at: str | None


class ProjectSkillCapabilities(BaseModel):
    can_edit: bool
    can_admin: bool


class ProjectSkillCatalogResponse(BaseModel):
    skills: list[SkillResponse]
    pending_change_requests: list[ChangeRequestResponse]
    capabilities: ProjectSkillCapabilities


class SkillDiffResponse(BaseModel):
    from_version: int
    to_version: int
    diff: str
