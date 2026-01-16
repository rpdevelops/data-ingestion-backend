"""
Repository for issue data access operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from src.models.issue import Issue, IssueItem, Staging
from src.app.logging_config import get_logger

logger = get_logger(__name__)


class IssueRepository:
    """Repository for issue operations."""
    
    @staticmethod
    def get_issues_by_job_id(
        db: Session,
        job_id: int,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> List[Issue]:
        """
        Get all issues for a specific job, with related staging rows.
        
        Args:
            db: Database session
            job_id: Job ID
            user_id: Optional user ID to verify job ownership
            request_id: Request ID for logging traceability
            
        Returns:
            List of Issue objects with loaded relationships
        """
        # First verify job exists and belongs to user (if user_id provided)
        from src.models.job import Job
        
        query = db.query(Job).filter(Job.job_id == job_id)
        if user_id:
            query = query.filter(Job.job_user_id == user_id)
        
        job = query.first()
        if not job:
            logger.warning(
                "Job not found or access denied",
                extra={
                    "request_id": request_id,
                    "job_id": job_id,
                    "user_id": user_id,
                }
            )
            return []
        
        # Get all issues for the job with relationships loaded using eager loading
        # This avoids N+1 queries by loading all related data in a single query
        issues = (
            db.query(Issue)
            .filter(Issue.issues_job_id == job_id)
            .options(
                # Eagerly load issue_items and their staging relationships
                joinedload(Issue.issue_items).joinedload(IssueItem.staging)
            )
            .order_by(desc(Issue.issue_created_at))
            .all()
        )
        
        logger.debug(
            "Issues query completed",
            extra={
                "request_id": request_id,
                "job_id": job_id,
                "issue_count": len(issues),
            }
        )
        
        return issues
    
    @staticmethod
    def count_issues_by_job_id(
        db: Session,
        job_id: int,
        user_id: Optional[str] = None
    ) -> tuple[int, int, int]:
        """
        Count total, resolved, and unresolved issues for a job.
        
        Args:
            db: Database session
            job_id: Job ID
            user_id: Optional user ID to verify job ownership
            
        Returns:
            Tuple of (total_count, resolved_count, unresolved_count)
        """
        # Verify job exists and belongs to user (if user_id provided)
        from src.models.job import Job
        
        query = db.query(Job).filter(Job.job_id == job_id)
        if user_id:
            query = query.filter(Job.job_user_id == user_id)
        
        job = query.first()
        if not job:
            return (0, 0, 0)
        
        # Count issues
        total = db.query(Issue).filter(Issue.issues_job_id == job_id).count()
        resolved = db.query(Issue).filter(
            Issue.issues_job_id == job_id,
            Issue.issue_resolved == True
        ).count()
        unresolved = total - resolved
        
        return (total, resolved, unresolved)
    
    @staticmethod
    def get_all_issues_by_user_id(
        db: Session,
        user_id: str,
        request_id: Optional[str] = None
    ) -> List[Issue]:
        """
        Get all issues for all jobs belonging to a specific user, with related staging rows.
        
        Args:
            db: Database session
            user_id: User ID to filter jobs
            request_id: Request ID for logging traceability
            
        Returns:
            List of Issue objects with loaded relationships, ordered by creation date (newest first)
        """
        from src.models.job import Job
        
        # Get all issues for jobs belonging to the user with relationships loaded using eager loading
        # This avoids N+1 queries by loading all related data in a single query
        issues = (
            db.query(Issue)
            .join(Job, Issue.issues_job_id == Job.job_id)
            .filter(Job.job_user_id == user_id)
            .options(
                # Eagerly load issue_items and their staging relationships
                joinedload(Issue.issue_items).joinedload(IssueItem.staging)
            )
            .order_by(desc(Issue.issue_created_at))
            .all()
        )
        
        logger.debug(
            "All issues query completed for user",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "issue_count": len(issues),
            }
        )
        
        return issues
    
    @staticmethod
    def count_all_issues_by_user_id(
        db: Session,
        user_id: str
    ) -> tuple[int, int, int]:
        """
        Count total, resolved, and unresolved issues for all jobs of a user.
        
        Args:
            db: Database session
            user_id: User ID to filter jobs
            
        Returns:
            Tuple of (total_count, resolved_count, unresolved_count)
        """
        from src.models.job import Job
        
        # Count issues for all jobs belonging to the user
        total = (
            db.query(Issue)
            .join(Job, Issue.issues_job_id == Job.job_id)
            .filter(Job.job_user_id == user_id)
            .count()
        )
        resolved = (
            db.query(Issue)
            .join(Job, Issue.issues_job_id == Job.job_id)
            .filter(
                Job.job_user_id == user_id,
                Issue.issue_resolved == True
            )
            .count()
        )
        unresolved = total - resolved
        
        return (total, resolved, unresolved)
