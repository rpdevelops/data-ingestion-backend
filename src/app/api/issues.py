"""
Issues API endpoints.

Authentication and Authorization:
- GET endpoints require authentication via JWT token (Depends(get_current_user))
- PUT endpoint requires authentication + "editor" group (Depends(require_group("editor")))
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from src.app.db.database import get_db
from src.app.auth.cognito_auth import get_current_user, require_group
from src.app.repository.job_repository import JobRepository
from src.app.repository.issue_repository import IssueRepository
from src.schemas.issue import IssueListResponse, IssueResponse, StagingRowResponse, IssueUpdateRequest
from src.app.logging_config import get_logger

logger = get_logger(__name__)


router = APIRouter(prefix="/issues", tags=["issues"])


@router.get(
    "",
    response_model=IssueListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all issues for user's jobs",
    description="""
    Get all issues for all jobs belonging to the authenticated user, including the staging rows that caused each issue.
    
    **Authentication**: Required (JWT token)
    **Authorization**: No group required (any authenticated user can access their own issues)
    
    Returns issues with related staging rows (excluding staging_row_hash and issue_key for idempotency).
    Issues are ordered by creation date (newest first).
    """
)
def get_all_user_issues(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ← AUTHENTICATION: Requires valid JWT token
):
    """
    Get all issues for all jobs belonging to the authenticated user.
    
    Returns issues with the staging rows that caused each issue.
    Excludes staging_row_hash and issue_key (used only for idempotency).
    
    Args:
        request: FastAPI request object (for request_id)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        IssueListResponse with issues, total count, resolved and unresolved counts
        
    Raises:
        HTTPException 401: If authentication fails
    """
    request_id = getattr(request.state, "request_id", None)
    user_id = current_user["user_id"]
    
    logger.info(
        "Fetching all issues for user",
        extra={
            "request_id": request_id,
            "user_id": user_id,
        }
    )
    
    # Get all issues for all jobs belonging to the user
    issues = IssueRepository.get_all_issues_by_user_id(db, user_id, request_id)
    total, resolved, unresolved = IssueRepository.count_all_issues_by_user_id(db, user_id)
    
    # Build response with staging rows
    issue_responses = []
    for issue in issues:
        # Get staging rows for this issue
        affected_rows = []
        for item in issue.issue_items:
            if item.staging:
                # Create staging response without staging_row_hash
                affected_rows.append(StagingRowResponse(
                    staging_id=item.staging.staging_id,
                    staging_email=item.staging.staging_email,
                    staging_first_name=item.staging.staging_first_name,
                    staging_last_name=item.staging.staging_last_name,
                    staging_company=item.staging.staging_company,
                    staging_created_at=item.staging.staging_created_at,
                    staging_status=item.staging.staging_status,
                ))
        
        # Create issue response without issue_key
        issue_responses.append(IssueResponse(
            issue_id=issue.issue_id,
            issues_job_id=issue.issues_job_id,
            issue_type=issue.issue_type,
            issue_resolved=issue.issue_resolved,
            issue_description=issue.issue_description,
            issue_resolved_at=issue.issue_resolved_at,
            issue_resolved_by=issue.issue_resolved_by,
            issue_resolution_comment=issue.issue_resolution_comment,
            issue_created_at=issue.issue_created_at,
            affected_rows=affected_rows,
        ))
    
    logger.info(
        "All issues fetched successfully",
        extra={
            "request_id": request_id,
            "user_id": user_id,
            "total_issues": total,
            "resolved": resolved,
            "unresolved": unresolved,
        }
    )
    
    return IssueListResponse(
        issues=issue_responses,
        total=total,
        resolved_count=resolved,
        unresolved_count=unresolved,
    )


@router.get(
    "/job/{job_id}",
    response_model=IssueListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get issues for a job",
    description="""
    Get all issues for a specific job, including the staging rows that caused each issue.
    
    **Authentication**: Required (JWT token)
    **Authorization**: No group required (any authenticated user can access their own job issues)
    
    Returns issues with related staging rows (excluding staging_row_hash and issue_key for idempotency).
    """
)
def get_job_issues(
    request: Request,
    job_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ← AUTHENTICATION: Requires valid JWT token
):
    """
    Get all issues for a specific job.
    
    Returns issues with the staging rows that caused each issue.
    Excludes staging_row_hash and issue_key (used only for idempotency).
    
    Args:
        request: FastAPI request object (for request_id)
        job_id: Job ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        IssueListResponse with issues, total count, resolved and unresolved counts
        
    Raises:
        HTTPException 404: If job not found or user doesn't have access
        HTTPException 401: If authentication fails
    """
    request_id = getattr(request.state, "request_id", None)
    user_id = current_user["user_id"]
    
    logger.info(
        "Fetching issues for job",
        extra={
            "request_id": request_id,
            "job_id": job_id,
            "user_id": user_id,
        }
    )
    
    # Verify job exists and belongs to user
    job = JobRepository.get_job_by_id(db, job_id, user_id)
    if not job:
        logger.warning(
            "Job not found or access denied",
            extra={
                "request_id": request_id,
                "job_id": job_id,
                "user_id": user_id,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or you don't have access to it"
        )
    
    # Get issues with staging rows
    issues = IssueRepository.get_issues_by_job_id(db, job_id, user_id, request_id)
    total, resolved, unresolved = IssueRepository.count_issues_by_job_id(db, job_id, user_id)
    
    # Build response with staging rows
    issue_responses = []
    for issue in issues:
        # Get staging rows for this issue
        affected_rows = []
        for item in issue.issue_items:
            if item.staging:
                # Create staging response without staging_row_hash
                affected_rows.append(StagingRowResponse(
                    staging_id=item.staging.staging_id,
                    staging_email=item.staging.staging_email,
                    staging_first_name=item.staging.staging_first_name,
                    staging_last_name=item.staging.staging_last_name,
                    staging_company=item.staging.staging_company,
                    staging_created_at=item.staging.staging_created_at,
                    staging_status=item.staging.staging_status,
                ))
        
        # Create issue response without issue_key
        issue_responses.append(IssueResponse(
            issue_id=issue.issue_id,
            issues_job_id=issue.issues_job_id,
            issue_type=issue.issue_type,
            issue_resolved=issue.issue_resolved,
            issue_description=issue.issue_description,
            issue_resolved_at=issue.issue_resolved_at,
            issue_resolved_by=issue.issue_resolved_by,
            issue_resolution_comment=issue.issue_resolution_comment,
            issue_created_at=issue.issue_created_at,
            affected_rows=affected_rows,
        ))
    
    logger.info(
        "Issues fetched successfully",
        extra={
            "request_id": request_id,
            "job_id": job_id,
            "total_issues": total,
            "resolved": resolved,
            "unresolved": unresolved,
        }
    )
    
    return IssueListResponse(
        issues=issue_responses,
        total=total,
        resolved_count=resolved,
        unresolved_count=unresolved,
    )


@router.get(
    "/{issue_id}",
    response_model=IssueResponse,
    status_code=status.HTTP_200_OK,
    summary="Get issue details",
    description="""
    Get detailed information about a specific issue, including all staging rows that caused it.
    
    **Authentication**: Required (JWT token)
    **Authorization**: No group required (any authenticated user can access their own issues)
    
    Returns issue with all fields (excluding issue_key) and all related staging rows (excluding staging_row_hash).
    """
)
def get_issue_details(
    request: Request,
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ← AUTHENTICATION: Requires valid JWT token
):
    """
    Get detailed information about a specific issue.
    
    Returns issue with all fields (excluding issue_key) and all related staging rows (excluding staging_row_hash).
    
    Args:
        request: FastAPI request object (for request_id)
        issue_id: Issue ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        IssueResponse with issue details and all related staging rows
        
    Raises:
        HTTPException 404: If issue not found or user doesn't have access
        HTTPException 401: If authentication fails
    """
    request_id = getattr(request.state, "request_id", None)
    user_id = current_user["user_id"]
    
    logger.info(
        "Fetching issue details",
        extra={
            "request_id": request_id,
            "issue_id": issue_id,
            "user_id": user_id,
        }
    )
    
    # Get issue with staging rows (verifies ownership)
    issue = IssueRepository.get_issue_by_id(db, issue_id, user_id, request_id)
    if not issue:
        logger.warning(
            "Issue not found or access denied",
            extra={
                "request_id": request_id,
                "issue_id": issue_id,
                "user_id": user_id,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue {issue_id} not found or you don't have access to it"
        )
    
    # Build response with staging rows
    affected_rows = []
    for item in issue.issue_items:
        if item.staging:
            # Create staging response without staging_row_hash
            affected_rows.append(StagingRowResponse(
                staging_id=item.staging.staging_id,
                staging_email=item.staging.staging_email,
                staging_first_name=item.staging.staging_first_name,
                staging_last_name=item.staging.staging_last_name,
                staging_company=item.staging.staging_company,
                staging_created_at=item.staging.staging_created_at,
                staging_status=item.staging.staging_status,
            ))
    
    # Create issue response without issue_key
    issue_response = IssueResponse(
        issue_id=issue.issue_id,
        issues_job_id=issue.issues_job_id,
        issue_type=issue.issue_type,
        issue_resolved=issue.issue_resolved,
        issue_description=issue.issue_description,
        issue_resolved_at=issue.issue_resolved_at,
        issue_resolved_by=issue.issue_resolved_by,
        issue_resolution_comment=issue.issue_resolution_comment,
        issue_created_at=issue.issue_created_at,
        affected_rows=affected_rows,
    )
    
    logger.info(
        "Issue details fetched successfully",
        extra={
            "request_id": request_id,
            "issue_id": issue_id,
            "user_id": user_id,
            "affected_rows_count": len(affected_rows),
        }
    )
    
    return issue_response


@router.put(
    "/{issue_id}",
    response_model=IssueResponse,
    status_code=status.HTTP_200_OK,
    summary="Update issue",
    description="""
    Update an issue by ID.
    
    **Authentication**: Required (JWT token)
    **Authorization**: Requires "editor" group
    
    Only provided fields will be updated. Fields not included in the request will remain unchanged.
    When resolving an issue (issue_resolved=true), issue_resolved_at is automatically set if not already set.
    When unresolving an issue (issue_resolved=false), issue_resolved_at and issue_resolved_by are cleared.
    """
)
def update_issue(
    request: Request,
    issue_id: int,
    issue_update: IssueUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_group("editor")),  # ← Requires "editor" group
):
    """
    Update an issue.
    
    Only provided fields will be updated. Fields not included in the request will remain unchanged.
    Verifies that the issue belongs to a job owned by the authenticated user.
    
    Args:
        request: FastAPI request object (for request_id)
        issue_id: Issue ID
        issue_update: Issue update data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        IssueResponse with updated issue and all related staging rows
        
    Raises:
        HTTPException 404: If issue not found or user doesn't have access
        HTTPException 401: If authentication fails
        HTTPException 403: If user doesn't belong to "editor" group
        HTTPException 400: If invalid data provided
    """
    request_id = getattr(request.state, "request_id", None)
    user_id = current_user["user_id"]
    
    logger.info(
        "Updating issue",
        extra={
            "request_id": request_id,
            "issue_id": issue_id,
            "user_id": user_id,
        }
    )
    
    # Update issue (verifies ownership)
    # If resolving and resolved_by not provided, use current user_id
    resolved_by = issue_update.issue_resolved_by
    if issue_update.issue_resolved is True and resolved_by is None:
        resolved_by = user_id
    
    updated_issue = IssueRepository.update_issue(
        db=db,
        issue_id=issue_id,
        user_id=user_id,
        resolved=issue_update.issue_resolved,
        description=issue_update.issue_description,
        resolved_by=resolved_by,
        resolution_comment=issue_update.issue_resolution_comment,
        request_id=request_id
    )
    
    if not updated_issue:
        logger.warning(
            "Issue not found or access denied",
            extra={
                "request_id": request_id,
                "issue_id": issue_id,
                "user_id": user_id,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue {issue_id} not found or you don't have access to it"
        )
    
    # Reload issue with relationships for response
    issue = IssueRepository.get_issue_by_id(db, issue_id, user_id, request_id)
    
    # Build response with staging rows
    affected_rows = []
    for item in issue.issue_items:
        if item.staging:
            # Create staging response without staging_row_hash
            affected_rows.append(StagingRowResponse(
                staging_id=item.staging.staging_id,
                staging_email=item.staging.staging_email,
                staging_first_name=item.staging.staging_first_name,
                staging_last_name=item.staging.staging_last_name,
                staging_company=item.staging.staging_company,
                staging_created_at=item.staging.staging_created_at,
                staging_status=item.staging.staging_status,
            ))
    
    # Create issue response without issue_key
    issue_response = IssueResponse(
        issue_id=issue.issue_id,
        issues_job_id=issue.issues_job_id,
        issue_type=issue.issue_type,
        issue_resolved=issue.issue_resolved,
        issue_description=issue.issue_description,
        issue_resolved_at=issue.issue_resolved_at,
        issue_resolved_by=issue.issue_resolved_by,
        issue_resolution_comment=issue.issue_resolution_comment,
        issue_created_at=issue.issue_created_at,
        affected_rows=affected_rows,
    )
    
    logger.info(
        "Issue updated successfully",
        extra={
            "request_id": request_id,
            "issue_id": issue_id,
            "user_id": user_id,
        }
    )
    
    return issue_response
