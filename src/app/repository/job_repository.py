"""
Repository for job data access operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models.job import Job
from src.schemas.job import JobResponse
from src.app.logging_config import get_logger

logger = get_logger(__name__)


class JobRepository:
    """Repository for job operations."""
    
    @staticmethod
    def get_all_jobs(db: Session, user_id: Optional[str] = None, request_id: Optional[str] = None) -> List[Job]:
        """
        Get all jobs, optionally filtered by user_id.
        
        Args:
            db: Database session
            user_id: Optional user ID to filter jobs
            request_id: Request ID for logging traceability
            
        Returns:
            List of Job objects
        """
        query = db.query(Job)
        
        if user_id:
            logger.debug(
                "Filtering jobs by user_id",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                }
            )
            query = query.filter(Job.job_user_id == user_id)
        
        jobs = query.order_by(desc(Job.job_created_at)).all()
        
        logger.debug(
            "Jobs query completed",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "job_count": len(jobs),
            }
        )
        
        return jobs
    
    @staticmethod
    def get_job_by_id(db: Session, job_id: int, user_id: Optional[str] = None) -> Optional[Job]:
        """
        Get a job by ID, optionally filtered by user_id.
        
        Args:
            db: Database session
            job_id: Job ID
            user_id: Optional user ID to verify ownership
            
        Returns:
            Job object or None if not found
        """
        query = db.query(Job).filter(Job.job_id == job_id)
        
        if user_id:
            query = query.filter(Job.job_user_id == user_id)
        
        return query.first()
    
    @staticmethod
    def count_jobs(db: Session, user_id: Optional[str] = None) -> int:
        """
        Count total number of jobs, optionally filtered by user_id.
        
        Args:
            db: Database session
            user_id: Optional user ID to filter jobs
            
        Returns:
            Total count of jobs
        """
        query = db.query(Job)
        
        if user_id:
            query = query.filter(Job.job_user_id == user_id)
        
        return query.count()
