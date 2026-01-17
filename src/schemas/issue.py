"""
Pydantic schemas for issues API requests and responses.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from src.models.issue import IssueType, StagingStatus


class StagingRowResponse(BaseModel):
    """Staging row response schema (without staging_row_hash)."""
    staging_id: int
    staging_email: Optional[str] = None
    staging_first_name: Optional[str] = None
    staging_last_name: Optional[str] = None
    staging_company: Optional[str] = None
    staging_created_at: datetime
    staging_status: Optional[StagingStatus] = None
    
    class Config:
        from_attributes = True


class IssueResponse(BaseModel):
    """Issue response schema (without issue_key)."""
    issue_id: int
    issues_job_id: int
    issue_type: IssueType
    issue_resolved: bool
    issue_description: Optional[str] = None
    issue_resolved_at: Optional[datetime] = None
    issue_resolved_by: Optional[str] = None
    issue_resolution_comment: Optional[str] = None
    issue_created_at: datetime
    affected_rows: List[StagingRowResponse] = Field(default_factory=list, description="Staging rows that caused this issue")
    
    class Config:
        from_attributes = True


class IssueListResponse(BaseModel):
    """Response schema for list of issues."""
    issues: List[IssueResponse]
    total: int
    resolved_count: int
    unresolved_count: int


class IssueUpdateRequest(BaseModel):
    """Request schema for updating an issue."""
    issue_resolved: Optional[bool] = Field(None, description="Whether the issue is resolved")
    issue_description: Optional[str] = Field(None, description="Issue description")
    issue_resolved_by: Optional[str] = Field(None, description="User who resolved the issue")
    issue_resolution_comment: Optional[str] = Field(None, description="Resolution comment")
    
    class Config:
        from_attributes = True
