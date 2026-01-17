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
    
    @staticmethod
    def get_issue_by_id(
        db: Session,
        issue_id: int,
        user_id: str,
        request_id: Optional[str] = None
    ) -> Optional[Issue]:
        """
        Get a specific issue by ID, with related staging rows.
        Verifies that the issue belongs to a job owned by the user.
        
        Args:
            db: Database session
            issue_id: Issue ID
            user_id: User ID to verify job ownership
            request_id: Request ID for logging traceability
            
        Returns:
            Issue object with loaded relationships, or None if not found or access denied
        """
        from src.models.job import Job
        
        # Get issue with job join to verify ownership
        issue = (
            db.query(Issue)
            .join(Job, Issue.issues_job_id == Job.job_id)
            .filter(
                Issue.issue_id == issue_id,
                Job.job_user_id == user_id
            )
            .options(
                # Eagerly load issue_items and their staging relationships
                joinedload(Issue.issue_items).joinedload(IssueItem.staging)
            )
            .first()
        )
        
        if not issue:
            logger.warning(
                "Issue not found or access denied",
                extra={
                    "request_id": request_id,
                    "issue_id": issue_id,
                    "user_id": user_id,
                }
            )
            return None
        
        logger.debug(
            "Issue query completed",
            extra={
                "request_id": request_id,
                "issue_id": issue_id,
                "user_id": user_id,
            }
        )
        
        return issue
    
    @staticmethod
    def update_issue(
        db: Session,
        issue_id: int,
        user_id: str,
        resolved: Optional[bool] = None,
        description: Optional[str] = None,
        resolved_by: Optional[str] = None,
        resolution_comment: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Optional[Issue]:
        """
        Update an issue record.
        Verifies that the issue belongs to a job owned by the user.
        
        Args:
            db: Database session
            issue_id: Issue ID
            user_id: User ID to verify job ownership
            resolved: Optional resolved status to update
            description: Optional description to update
            resolved_by: Optional user who resolved the issue
            resolution_comment: Optional resolution comment
            request_id: Request ID for logging traceability
            
        Returns:
            Updated Issue object, or None if not found or access denied
        """
        from datetime import datetime
        
        # Get issue and verify ownership
        issue = IssueRepository.get_issue_by_id(db, issue_id, user_id, request_id)
        if not issue:
            return None
        
        # Update only provided fields
        if resolved is not None:
            issue.issue_resolved = resolved
            # If resolving, set resolved_at if not already set
            if resolved and not issue.issue_resolved_at:
                issue.issue_resolved_at = datetime.utcnow()
            # If unresolving, clear resolved_at and resolved_by
            elif not resolved:
                issue.issue_resolved_at = None
                issue.issue_resolved_by = None
        
        if description is not None:
            issue.issue_description = description
        
        if resolved_by is not None:
            issue.issue_resolved_by = resolved_by
            # If resolving and resolved_at not set, set it
            if issue.issue_resolved and not issue.issue_resolved_at:
                issue.issue_resolved_at = datetime.utcnow()
        
        if resolution_comment is not None:
            issue.issue_resolution_comment = resolution_comment
        
        db.commit()
        db.refresh(issue)
        
        logger.info(
            "Issue updated successfully",
            extra={
                "request_id": request_id,
                "issue_id": issue_id,
                "user_id": user_id,
            }
        )
        
        return issue
