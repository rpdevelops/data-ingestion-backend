"""
SQLAlchemy models for issues, issue_items, and staging tables.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from src.app.db.database import Base


class IssueType(str, enum.Enum):
    """Issue type enumeration."""
    DUPLICATE_EMAIL = "DUPLICATE_EMAIL"
    INVALID_EMAIL = "INVALID_EMAIL"
    EXISTING_EMAIL = "EXISTING_EMAIL"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"


class StagingStatus(str, enum.Enum):
    """Staging status enumeration."""
    READY = "READY"
    SUCCESS = "SUCCESS"
    DISCARD = "DISCARD"
    ISSUE = "ISSUE"


class Issue(Base):
    """Issue model representing the issues table."""
    
    __tablename__ = "issues"
    
    issue_id = Column(Integer, primary_key=True, index=True)
    issues_job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    issue_type = Column(SQLEnum(IssueType), nullable=False, index=True)
    issue_key = Column(String, nullable=False)
    issue_resolved = Column(Boolean, nullable=False, default=False, index=True)
    issue_description = Column(String, nullable=True)
    issue_resolved_at = Column(DateTime(timezone=True), nullable=True)
    issue_resolved_by = Column(String, nullable=True)
    issue_resolution_comment = Column(String, nullable=True)
    issue_created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    issue_items = relationship("IssueItem", back_populates="issue", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Issue(issue_id={self.issue_id}, type={self.issue_type}, resolved={self.issue_resolved})>"


class IssueItem(Base):
    """IssueItem model representing the issue_items table."""
    
    __tablename__ = "issue_items"
    
    issue_item_id = Column(Integer, primary_key=True, index=True)
    item_issue_id = Column(Integer, ForeignKey("issues.issue_id", ondelete="CASCADE"), nullable=False, index=True)
    item_staging_id = Column(BigInteger, ForeignKey("staging.staging_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationships
    issue = relationship("Issue", back_populates="issue_items")
    staging = relationship("Staging", back_populates="issue_items")
    
    def __repr__(self):
        return f"<IssueItem(issue_item_id={self.issue_item_id}, issue_id={self.item_issue_id}, staging_id={self.item_staging_id})>"


class Staging(Base):
    """Staging model representing the staging table."""
    
    __tablename__ = "staging"
    
    staging_id = Column(BigInteger, primary_key=True, index=True)
    staging_job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    staging_email = Column(String, nullable=True)
    staging_first_name = Column(String, nullable=True)
    staging_last_name = Column(String, nullable=True)
    staging_company = Column(String, nullable=True)
    staging_created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    staging_status = Column(SQLEnum(StagingStatus), nullable=True, index=True)
    staging_row_hash = Column(String, nullable=False)  # Not returned in API, only for idempotency
    
    # Relationships
    issue_items = relationship("IssueItem", back_populates="staging", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Staging(staging_id={self.staging_id}, job_id={self.staging_job_id}, status={self.staging_status})>"
