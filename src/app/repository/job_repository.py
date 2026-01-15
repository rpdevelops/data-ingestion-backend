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
    
    @staticmethod
    def create_job(
        db: Session,
        user_id: str,
        original_filename: str,
        s3_object_key: str,
        total_rows: int,
        request_id: Optional[str] = None
    ) -> Job:
        """
        Create a new job record.
        
        Args:
            db: Database session
            user_id: User ID from JWT token
            original_filename: Original CSV filename
            s3_object_key: S3 object key where file is stored
            total_rows: Total number of rows in CSV
            request_id: Request ID for logging traceability
            
        Returns:
            Created Job object
        """
        from src.models.job import JobStatus
        
        job = Job(
            job_user_id=user_id,
            job_original_filename=original_filename,
            job_s3_object_key=s3_object_key,
            job_status=JobStatus.PENDING,
            job_total_rows=total_rows,
            job_processed_rows=0,
            job_issue_count=0,
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        logger.info(
            "Job created successfully",
            extra={
                "request_id": request_id,
                "job_id": job.job_id,
                "user_id": user_id,
                "file_name": original_filename,
                "total_rows": total_rows,
            }
        )
        
        return job
    
    @staticmethod
    def check_duplicate_file(
        db: Session,
        user_id: str,
        filename: str,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Check if a file with the same name was already imported by this user.
        
        Args:
            db: Database session
            user_id: User ID
            filename: Filename to check
            request_id: Request ID for logging traceability
            
        Returns:
            True if duplicate exists, False otherwise
        """
        existing_job = db.query(Job).filter(
            Job.job_user_id == user_id,
            Job.job_original_filename == filename
        ).first()
        
        if existing_job:
            logger.warning(
                "Duplicate file detected",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "file_name": filename,
                    "existing_job_id": existing_job.job_id,
                }
            )
            return True
        
        return False
    
    @staticmethod
    def delete_job(
        db: Session,
        job_id: int,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Delete a job record from database.
        
        Args:
            db: Database session
            job_id: Job ID to delete
            request_id: Request ID for logging traceability
            
        Returns:
            True if job was deleted, False if job not found
        """
        job = db.query(Job).filter(Job.job_id == job_id).first()
        
        if not job:
            logger.warning(
                "Job not found for deletion",
                extra={
                    "request_id": request_id,
                    "job_id": job_id,
                }
            )
            return False
        
        db.delete(job)
        db.commit()
        
        logger.info(
            "Job deleted successfully",
            extra={
                "request_id": request_id,
                "job_id": job_id,
                "user_id": job.job_user_id,
            }
        )
        
        return True
