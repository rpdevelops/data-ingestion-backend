"""
Jobs API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional

from src.app.db.database import get_db
from src.app.auth.cognito_auth import get_current_user
from src.app.repository.job_repository import JobRepository
from src.schemas.job import JobResponse, JobListResponse
from src.app.logging_config import get_logger

logger = get_logger(__name__)


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse, status_code=status.HTTP_200_OK)
def get_all_jobs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    user_id: Optional[str] = None,
    debug: Optional[bool] = False,
):
    """
    Get all jobs.
    
    If user_id query parameter is provided, filters jobs by that user.
    Otherwise, returns all jobs (user can only see their own jobs by default).
    
    Args:
        request: FastAPI request object (for request_id)
        db: Database session
        current_user: Current authenticated user
        user_id: Optional user ID filter (defaults to current user)
        debug: If true, returns debug information and all jobs (for testing)
        
    Returns:
        List of jobs with total count
    """
    request_id = getattr(request.state, "request_id", None)
    filter_user_id = user_id if user_id == current_user["user_id"] else current_user["user_id"]
    
    # Log request with structured data
    logger.info(
        "Fetching jobs",
        extra={
            "request_id": request_id,
            "user_id": current_user["user_id"],
            "filter_user_id": filter_user_id,
            "debug_mode": debug,
        }
    )
    
    # Debug mode: return all jobs and show what user_id is being used
    if debug:
        logger.debug(
            "Debug mode enabled",
            extra={
                "request_id": request_id,
                "filter_user_id": filter_user_id,
            }
        )
        all_jobs = JobRepository.get_all_jobs(db, user_id=None)
        logger.debug(
            f"Total jobs in DB: {len(all_jobs)}",
            extra={"request_id": request_id}
        )
    
    # Get all jobs for the user
    jobs = JobRepository.get_all_jobs(db, user_id=filter_user_id, request_id=request_id)
    total = JobRepository.count_jobs(db, user_id=filter_user_id)
    
    # Log response with structured data
    logger.info(
        "Jobs fetched successfully",
        extra={
            "request_id": request_id,
            "user_id": filter_user_id,
            "job_count": total,
        }
    )
    
    return JobListResponse(
        jobs=[JobResponse.model_validate(job) for job in jobs],
        total=total,
    )
