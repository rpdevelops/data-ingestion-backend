"""
Pydantic schemas for CSV upload API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Optional


class UploadResponse(BaseModel):
    """Response schema for CSV upload."""
    job_id: int = Field(..., description="ID of the created job")
    message: str = Field(..., description="Success message")
    filename: str = Field(..., description="Original filename")
    total_rows: int = Field(..., description="Total number of rows in the CSV")


class UploadErrorResponse(BaseModel):
    """Error response schema for CSV upload."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
