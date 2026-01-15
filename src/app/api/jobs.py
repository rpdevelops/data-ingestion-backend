"""
Jobs API endpoints.

Authentication and Authorization:
- All endpoints require authentication via JWT token (Depends(get_current_user))
- Some endpoints require specific Cognito groups (Depends(require_group("uploader")))
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from src.app.db.database import get_db
from src.app.auth.cognito_auth import get_current_user, require_group
from src.app.repository.job_repository import JobRepository
from src.schemas.job import JobResponse, JobListResponse
from src.schemas.upload import UploadResponse, UploadErrorResponse
from src.app.services.csv_validator import csv_validator
from src.app.services.s3_service import s3_service
from src.app.services.sqs_service import sqs_service
from src.app.logging_config import get_logger
from src.settings import settings

logger = get_logger(__name__)


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all jobs",
    description="""
    Get all jobs for the authenticated user.
    
    **Authentication**: Required (JWT token)
    **Authorization**: No group required (any authenticated user can access their own jobs)
    
    Returns only jobs owned by the authenticated user (filtered by user_id from JWT token).
    """
)
def get_all_jobs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ← AUTHENTICATION: Requires valid JWT token
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


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload CSV file",
    description="""
    Upload a CSV file for processing.
    
    **Authentication**: Required (JWT token)
    **Authorization**: Requires "uploader" group
    
    This endpoint:
    1. Validates JWT token and user group
    2. Validates CSV file (format, size < 5MB, not empty, has data)
    3. Checks for duplicate files
    4. Uploads file to S3
    5. Creates job record in database
    6. Publishes message to SQS queue for worker processing
    7. Returns job ID and file information
    """
)
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_group("uploader")),  # ← Requires "uploader" group
):
    """
    Upload CSV file for processing.
    
    This endpoint follows the upload flow specified in AGENT.md:
    1. Validate JWT token and verify IAM role (uploader)
    2. Pre-validate CSV file (format, size, duplicate check, empty check)
    3. Upload CSV to S3 private bucket
    4. Create job record in jobs table (status: PENDING)
    5. Publish message to SQS queue
    6. Return job_id to frontend
    
    Args:
        request: FastAPI request object (for request_id)
        file: CSV file to upload
        db: Database session
        current_user: Current authenticated user (must belong to "uploader" group)
        
    Returns:
        UploadResponse with job_id, message, filename, and total_rows
        
    Raises:
        HTTPException 400: If file validation fails
        HTTPException 401: If authentication fails
        HTTPException 403: If user doesn't belong to "uploader" group
        HTTPException 409: If file was already imported (duplicate)
        HTTPException 500: If upload or processing fails
    """
    request_id = getattr(request.state, "request_id", None)
    user_id = current_user["user_id"]
    
    logger.info(
        "CSV upload request received",
        extra={
            "request_id": request_id,
            "user_id": user_id,
            "file_name": file.filename,
        }
    )
    
    try:
        # Step 1: Validate JWT token and group (already done by require_group dependency)
        
        # Step 2: Pre-validate CSV file
        logger.info(
            "Validating CSV file",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "file_name": file.filename,
            }
        )
        
        file_content, total_rows, file_hash = await csv_validator.validate_upload_file(file)
        
        # Step 3: Check for duplicate file (by filename for same user)
        if JobRepository.check_duplicate_file(db, user_id, file.filename, request_id):
            logger.warning(
                "Duplicate file rejected",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "file_name": file.filename,
                }
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File '{file.filename}' has already been imported. Please use a different filename."
            )
        
        # Step 4: Upload CSV to S3
        logger.info(
            "Uploading file to S3",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "file_name": file.filename,
            }
        )
        
        try:
            s3_key = s3_service.upload_csv_file(
                file_content=file_content,
                original_filename=file.filename,
                user_id=user_id
            )
        except Exception as e:
            logger.error(
                "S3 upload failed",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "file_name": file.filename,
                    "error": str(e),
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to storage: {str(e)}"
            )
        
        # Step 5: Create job record in database
            logger.info(
                "Creating job record",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "file_name": file.filename,
                    "s3_key": s3_key,
                    "total_rows": total_rows,
                }
            )
        
        try:
            job = JobRepository.create_job(
                db=db,
                user_id=user_id,
                original_filename=file.filename,
                s3_object_key=s3_key,
                total_rows=total_rows,
                request_id=request_id
            )
        except Exception as e:
            logger.error(
                "Job creation failed",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "file_name": file.filename,
                    "s3_key": s3_key,
                    "error": str(e),
                },
                exc_info=True
            )
            # Note: File is already in S3, but job creation failed
            # In production, you might want to clean up the S3 file here
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create job record: {str(e)}"
            )
        
        # Step 6: Publish message to SQS queue
        logger.info(
            "Publishing message to SQS",
            extra={
                "request_id": request_id,
                "job_id": job.job_id,
                "s3_key": s3_key,
            }
        )
        
        try:
            sqs_service.publish_job_message(
                job_id=job.job_id,
                s3_key=s3_key
            )
        except Exception as e:
            error_message = str(e)
            logger.error(
                "SQS publish failed - rolling back job and S3 file",
                extra={
                    "request_id": request_id,
                    "job_id": job.job_id,
                    "s3_key": s3_key,
                    "error": error_message,
                },
                exc_info=True
            )
            
            # Rollback: Delete job from database
            try:
                JobRepository.delete_job(db, job.job_id, request_id)
                logger.info(
                    "Job deleted during rollback",
                    extra={
                        "request_id": request_id,
                        "job_id": job.job_id,
                    }
                )
            except Exception as delete_error:
                logger.error(
                    "Failed to delete job during rollback",
                    extra={
                        "request_id": request_id,
                        "job_id": job.job_id,
                        "error": str(delete_error),
                    },
                    exc_info=True
                )
            
            # Rollback: Delete file from S3
            try:
                s3_service.delete_file(s3_key)
                logger.info(
                    "S3 file deleted during rollback",
                    extra={
                        "request_id": request_id,
                        "s3_key": s3_key,
                    }
                )
            except Exception as delete_error:
                logger.error(
                    "Failed to delete S3 file during rollback",
                    extra={
                        "request_id": request_id,
                        "s3_key": s3_key,
                        "error": str(delete_error),
                    },
                    exc_info=True
                )
            
            # Raise HTTPException to inform the user
            if "does not exist" in error_message or "NonExistentQueue" in error_message:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"SQS queue does not exist. "
                        f"Please create the SQS queue or fix SQS_QUEUE_URL environment variable. "
                        f"Upload has been rolled back."
                    )
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"Failed to publish message to SQS queue. "
                        f"Upload has been rolled back. Error: {error_message}"
                    )
                )
        
        # Step 7: Return success response
        logger.info(
            "CSV upload completed successfully",
            extra={
                "request_id": request_id,
                "job_id": job.job_id,
                "user_id": user_id,
                "file_name": file.filename,
                "total_rows": total_rows,
            }
        )
        
        return UploadResponse(
            job_id=job.job_id,
            message=f"File '{file.filename}' uploaded successfully and queued for processing",
            filename=file.filename,
            total_rows=total_rows,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, etc.)
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during CSV upload",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "file_name": file.filename if file else None,
                "error": str(e),
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )
