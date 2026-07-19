"""Thin authenticated API for project-scoped, staged skill approvals."""

from __future__ import annotations

import difflib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models import (
    ProjectSkill,
    ProjectSkillChangeRequest,
    ProjectSkillVersion,
    ProjectSkillVersionScan,
    User,
)
from src.schemas.project_skills import (
    ApprovalRequest,
    ChangeRequestResponse,
    ProjectSkillCapabilities,
    ProjectSkillCatalogResponse,
    RejectRequest,
    RollbackRequest,
    SkillDiffResponse,
    SkillDocumentRequest,
    SkillResponse,
    SkillVersionResponse,
)
from src.services.project_skills.access import ProjectSkillNotFound
from src.services.project_skills.approval_service import (
    ProjectSkillApprovalError,
    ProjectSkillApprovalService,
    ProjectSkillConflict,
)
from src.services.project_skills.catalog_service import (
    ProjectSkillCatalogError,
    ProjectSkillCatalogService,
    ProjectSkillProposalConflict,
)
from src.services.project_skills.skill_document import SkillDocumentError

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/skills", tags=["project-skills"]
)


async def _version_response(
    db: AsyncSession, version: ProjectSkillVersion
) -> SkillVersionResponse:
    scan = await db.scalar(
        select(ProjectSkillVersionScan)
        .where(ProjectSkillVersionScan.version_id == version.id)
        .order_by(
            ProjectSkillVersionScan.created_at.desc(), ProjectSkillVersionScan.id.desc()
        )
        .limit(1)
    )
    return SkillVersionResponse(
        id=version.id,
        version=version.version,
        name=version.parsed_name,
        description=version.description,
        content_hash=version.content_hash,
        document_text=version.instructions,
        scan_state=scan.scan_state if scan is not None else "error",
        scan_findings=scan.findings if scan is not None else [],
    )


async def _skill_response(
    db: AsyncSession, skill, versions: list[ProjectSkillVersion] | None = None
) -> SkillResponse:
    active_version = (
        await db.get(ProjectSkillVersion, skill.active_version_id)
        if skill.active_version_id is not None
        else None
    )
    return SkillResponse(
        id=skill.id,
        name=skill.normalized_name,
        active_version_id=skill.active_version_id,
        is_archived=skill.is_archived,
        active_version=(
            await _version_response(db, active_version)
            if active_version is not None
            else None
        ),
        versions=[await _version_response(db, version) for version in versions or []],
    )


async def _request_response(
    db: AsyncSession, request: ProjectSkillChangeRequest
) -> ChangeRequestResponse:
    skill_name = await db.scalar(
        select(ProjectSkill.normalized_name).where(ProjectSkill.id == request.skill_id)
    )
    return ChangeRequestResponse(
        id=request.id,
        action=request.action,
        status=request.status,
        proposed_version_id=request.proposed_version_id,
        expected_active_version_id=request.expected_active_version_id,
        audit_note=request.audit_note,
        skill_id=request.skill_id,
        skill_name=skill_name,
        requester_id=request.requester_id,
        reviewer_id=request.reviewer_id,
        warning_acknowledged=request.warning_acknowledged,
        created_at=request.created_at,
        reviewed_at=request.reviewed_at,
    )


def _translate_error(error: Exception) -> None:
    if isinstance(error, ProjectSkillNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project or skill not found"
        ) from error
    if isinstance(error, (ProjectSkillConflict, ProjectSkillProposalConflict)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    if isinstance(
        error, (ProjectSkillCatalogError, ProjectSkillApprovalError, SkillDocumentError)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    raise error


@router.get("", response_model=ProjectSkillCatalogResponse)
async def list_skills(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        skills, pending, capabilities = await ProjectSkillCatalogService(
            db
        ).list_catalog(project_id=project_id, user_id=current_user.id)
        return ProjectSkillCatalogResponse(
            skills=[await _skill_response(db, skill) for skill in skills],
            pending_change_requests=[
                await _request_response(db, request) for request in pending
            ],
            capabilities=ProjectSkillCapabilities(**capabilities),
        )
    except Exception as error:
        _translate_error(error)


@router.post(
    "", response_model=ChangeRequestResponse, status_code=status.HTTP_201_CREATED
)
async def create_skill(
    project_id: UUID,
    payload: SkillDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        _skill, _version, request = await ProjectSkillCatalogService(db).create_skill(
            project_id=project_id,
            user_id=current_user.id,
            document_text=payload.document_text,
        )
        return await _request_response(db, request)
    except Exception as error:
        _translate_error(error)


@router.post(
    "/change-requests/{request_id}/approve", response_model=ChangeRequestResponse
)
async def approve_change_request(
    project_id: UUID,
    request_id: UUID,
    payload: ApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        request = await ProjectSkillApprovalService(db).approve(
            project_id=project_id,
            request_id=request_id,
            user_id=current_user.id,
            self_approval_acknowledged=payload.self_approval_acknowledged,
            warning_acknowledged=payload.warning_acknowledged,
            audit_note=payload.audit_note,
        )
        return await _request_response(db, request)
    except Exception as error:
        _translate_error(error)


@router.post(
    "/change-requests/{request_id}/reject", response_model=ChangeRequestResponse
)
async def reject_change_request(
    project_id: UUID,
    request_id: UUID,
    payload: RejectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        request = await ProjectSkillApprovalService(db).reject(
            project_id=project_id,
            request_id=request_id,
            user_id=current_user.id,
            audit_note=payload.audit_note,
        )
        return await _request_response(db, request)
    except Exception as error:
        _translate_error(error)


@router.post(
    "/change-requests/{request_id}/rescan", response_model=SkillVersionResponse
)
async def rescan_change_request(
    project_id: UUID,
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        version, _scan = await ProjectSkillApprovalService(db).rescan_change_request(
            project_id=project_id, request_id=request_id, user_id=current_user.id
        )
        return await _version_response(db, version)
    except Exception as error:
        _translate_error(error)


@router.post(
    "/{skill_name}/versions",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def propose_version(
    project_id: UUID,
    skill_name: str,
    payload: SkillDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        _version, request = await ProjectSkillCatalogService(db).propose_version(
            project_id=project_id,
            skill_name=skill_name,
            user_id=current_user.id,
            document_text=payload.document_text,
        )
        return await _request_response(db, request)
    except Exception as error:
        _translate_error(error)


@router.post(
    "/{skill_name}/archive",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def archive_skill(
    project_id: UUID,
    skill_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        request = await ProjectSkillCatalogService(db).stage_state_change(
            project_id=project_id,
            skill_name=skill_name,
            user_id=current_user.id,
            action="archive",
        )
        return await _request_response(db, request)
    except Exception as error:
        _translate_error(error)


@router.post(
    "/{skill_name}/restore",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def restore_skill(
    project_id: UUID,
    skill_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        request = await ProjectSkillCatalogService(db).stage_state_change(
            project_id=project_id,
            skill_name=skill_name,
            user_id=current_user.id,
            action="restore",
        )
        return await _request_response(db, request)
    except Exception as error:
        _translate_error(error)


@router.post(
    "/{skill_name}/rollback",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rollback_skill(
    project_id: UUID,
    skill_name: str,
    payload: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        request = await ProjectSkillCatalogService(db).stage_state_change(
            project_id=project_id,
            skill_name=skill_name,
            user_id=current_user.id,
            action="rollback",
            target_version_id=payload.version_id,
        )
        return await _request_response(db, request)
    except Exception as error:
        _translate_error(error)


@router.get("/{skill_name}/diff", response_model=SkillDiffResponse)
async def diff_skill_versions(
    project_id: UUID,
    skill_name: str,
    from_version: int,
    to_version: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        skill = await ProjectSkillCatalogService(db).get_skill(
            project_id=project_id, skill_name=skill_name, user_id=current_user.id
        )
        versions = list(
            (
                await db.scalars(
                    select(ProjectSkillVersion).where(
                        ProjectSkillVersion.skill_id == skill.id,
                        ProjectSkillVersion.version.in_([from_version, to_version]),
                    )
                )
            ).all()
        )
        by_number = {version.version: version for version in versions}
        if from_version not in by_number or to_version not in by_number:
            raise ProjectSkillNotFound("skill version not found")
        diff = "".join(
            difflib.unified_diff(
                by_number[from_version].instructions.splitlines(keepends=True),
                by_number[to_version].instructions.splitlines(keepends=True),
                fromfile=f"v{from_version}",
                tofile=f"v{to_version}",
            )
        )
        return SkillDiffResponse(
            from_version=from_version, to_version=to_version, diff=diff
        )
    except Exception as error:
        _translate_error(error)


@router.get("/{skill_name}", response_model=SkillResponse)
async def get_skill(
    project_id: UUID,
    skill_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        skill = await ProjectSkillCatalogService(db).get_skill(
            project_id=project_id, skill_name=skill_name, user_id=current_user.id
        )
        versions = list(
            (
                await db.scalars(
                    select(ProjectSkillVersion)
                    .where(ProjectSkillVersion.skill_id == skill.id)
                    .order_by(ProjectSkillVersion.version.desc())
                )
            ).all()
        )
        return await _skill_response(db, skill, versions)
    except Exception as error:
        _translate_error(error)
