"""
Pydantic schemas for staging API requests and responses.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from src.models.issue import StagingStatus


class StagingUpdateRequest(BaseModel):
    """Request schema for updating a staging record."""
    staging_email: Optional[str] = Field(None, description="Email address")
    staging_first_name: Optional[str] = Field(None, description="First name")
    staging_last_name: Optional[str] = Field(None, description="Last name")
    staging_company: Optional[str] = Field(None, description="Company name")
    staging_status: Optional[StagingStatus] = Field(None, description="Staging status")
    
    class Config:
        from_attributes = True


class StagingResponse(BaseModel):
    """Staging response schema (without staging_row_hash)."""
    staging_id: int
    staging_job_id: int
    staging_email: Optional[str] = None
    staging_first_name: Optional[str] = None
    staging_last_name: Optional[str] = None
    staging_company: Optional[str] = None
    staging_created_at: datetime
    staging_status: Optional[StagingStatus] = None
    
    class Config:
        from_attributes = True
