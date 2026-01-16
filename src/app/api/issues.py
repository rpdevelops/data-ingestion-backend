"""
Issues API endpoints.

Authentication and Authorization:
- All endpoints require authentication via JWT token (Depends(get_current_user))
- No group required (any authenticated user can access their own issues)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from src.app.db.database import get_db
from src.app.auth.cognito_auth import get_current_user
from src.app.repository.job_repository import JobRepository
from src.app.repository.issue_repository import IssueRepository
from src.schemas.issue import IssueListResponse, IssueResponse, StagingRowResponse
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
