"""
Pydantic schemas for job API requests and responses.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from src.models.job import JobStatus


class JobBase(BaseModel):
    """Base job schema with common fields."""
    job_status: JobStatus
    job_total_rows: int = Field(ge=0)
    job_processed_rows: int = Field(ge=0)
    job_issue_count: int = Field(ge=0)


class JobResponse(JobBase):
    """Job response schema."""
    job_id: int
    job_created_at: datetime
    job_user_id: str
    job_original_filename: str
    job_s3_object_key: str
    job_process_start: Optional[datetime] = None
    job_process_end: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Response schema for list of jobs."""
    jobs: list[JobResponse]
    total: int
