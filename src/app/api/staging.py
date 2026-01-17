"""
Staging API endpoints.

Authentication and Authorization:
- All endpoints require authentication via JWT token
- Update endpoint requires "editor" group (Depends(require_group("editor")))
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from src.app.db.database import get_db
from src.app.auth.cognito_auth import get_current_user, require_group
from src.app.repository.staging_repository import StagingRepository
from src.schemas.staging import StagingUpdateRequest, StagingResponse
from src.app.logging_config import get_logger

logger = get_logger(__name__)


router = APIRouter(prefix="/staging", tags=["staging"])


@router.put(
    "/{staging_id}",
    response_model=StagingResponse,
    status_code=status.HTTP_200_OK,
    summary="Update staging record",
    description="""
    Update a staging record by ID.
    
    **Authentication**: Required (JWT token)
    **Authorization**: Requires "editor" group
    
    Only provided fields will be updated. Fields not included in the request will remain unchanged.
    """
)
def update_staging(
    request: Request,
    staging_id: int,
    staging_update: StagingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_group("editor")),  # ← Requires "editor" group
):
    """
    Update a staging record.
    
    Only provided fields will be updated. Fields not included in the request will remain unchanged.
    Verifies that the staging belongs to a job owned by the authenticated user.
    
    Args:
        request: FastAPI request object (for request_id)
        staging_id: Staging ID
        staging_update: Staging update data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        StagingResponse with updated staging record (excluding staging_row_hash)
        
    Raises:
        HTTPException 404: If staging not found or user doesn't have access
        HTTPException 401: If authentication fails
        HTTPException 403: If user doesn't belong to "editor" group
        HTTPException 400: If invalid data provided
    """
    request_id = getattr(request.state, "request_id", None)
    user_id = current_user["user_id"]
    
    logger.info(
        "Updating staging record",
        extra={
            "request_id": request_id,
            "staging_id": staging_id,
            "user_id": user_id,
        }
    )
    
    # Update staging (verifies ownership)
    updated_staging = StagingRepository.update_staging(
        db=db,
        staging_id=staging_id,
        user_id=user_id,
        email=staging_update.staging_email,
        first_name=staging_update.staging_first_name,
        last_name=staging_update.staging_last_name,
        company=staging_update.staging_company,
        status=staging_update.staging_status.value if staging_update.staging_status is not None else None,
        request_id=request_id
    )
    
    if not updated_staging:
        logger.warning(
            "Staging not found or access denied",
            extra={
                "request_id": request_id,
                "staging_id": staging_id,
                "user_id": user_id,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staging {staging_id} not found or you don't have access to it"
        )
    
    # Create response without staging_row_hash
    staging_response = StagingResponse(
        staging_id=updated_staging.staging_id,
        staging_job_id=updated_staging.staging_job_id,
        staging_email=updated_staging.staging_email,
        staging_first_name=updated_staging.staging_first_name,
        staging_last_name=updated_staging.staging_last_name,
        staging_company=updated_staging.staging_company,
        staging_created_at=updated_staging.staging_created_at,
        staging_status=updated_staging.staging_status,
    )
    
    logger.info(
        "Staging updated successfully",
        extra={
            "request_id": request_id,
            "staging_id": staging_id,
            "user_id": user_id,
        }
    )
    
    return staging_response
