"""
Repository for staging data access operations.
"""
from typing import Optional
from sqlalchemy.orm import Session

from src.models.issue import Staging
from src.app.logging_config import get_logger

logger = get_logger(__name__)


class StagingRepository:
    """Repository for staging operations."""
    
    @staticmethod
    def get_staging_by_id(
        db: Session,
        staging_id: int,
        user_id: str,
        request_id: Optional[str] = None
    ) -> Optional[Staging]:
        """
        Get a specific staging record by ID.
        Verifies that the staging belongs to a job owned by the user.
        
        Args:
            db: Database session
            staging_id: Staging ID
            user_id: User ID to verify job ownership
            request_id: Request ID for logging traceability
            
        Returns:
            Staging object, or None if not found or access denied
        """
        from src.models.job import Job
        
        # Get staging with job join to verify ownership
        staging = (
            db.query(Staging)
            .join(Job, Staging.staging_job_id == Job.job_id)
            .filter(
                Staging.staging_id == staging_id,
                Job.job_user_id == user_id
            )
            .first()
        )
        
        if not staging:
            logger.warning(
                "Staging not found or access denied",
                extra={
                    "request_id": request_id,
                    "staging_id": staging_id,
                    "user_id": user_id,
                }
            )
            return None
        
        logger.debug(
            "Staging query completed",
            extra={
                "request_id": request_id,
                "staging_id": staging_id,
                "user_id": user_id,
            }
        )
        
        return staging
    
    @staticmethod
    def update_staging(
        db: Session,
        staging_id: int,
        user_id: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company: Optional[str] = None,
        status: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Optional[Staging]:
        """
        Update a staging record.
        Verifies that the staging belongs to a job owned by the user.
        
        Args:
            db: Database session
            staging_id: Staging ID
            user_id: User ID to verify job ownership
            email: Optional email to update
            first_name: Optional first name to update
            last_name: Optional last name to update
            company: Optional company to update
            status: Optional status to update
            request_id: Request ID for logging traceability
            
        Returns:
            Updated Staging object, or None if not found or access denied
        """
        # Get staging and verify ownership
        staging = StagingRepository.get_staging_by_id(db, staging_id, user_id, request_id)
        if not staging:
            return None
        
        # Update only provided fields
        if email is not None:
            staging.staging_email = email
        if first_name is not None:
            staging.staging_first_name = first_name
        if last_name is not None:
            staging.staging_last_name = last_name
        if company is not None:
            staging.staging_company = company
        if status is not None:
            from src.models.issue import StagingStatus
            staging.staging_status = StagingStatus(status)
        
        db.commit()
        db.refresh(staging)
        
        logger.info(
            "Staging updated successfully",
            extra={
                "request_id": request_id,
                "staging_id": staging_id,
                "user_id": user_id,
            }
        )
        
        return staging
