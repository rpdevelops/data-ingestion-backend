"""
Pydantic schemas for contact API requests and responses.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class ContactResponse(BaseModel):
    """Contact response schema."""
    contact_id: int
    staging_id: int
    contacts_user_id: str
    contact_email: str
    contact_first_name: str
    contact_last_name: str
    contact_company: str
    contact_created_at: datetime
    
    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Response schema for list of contacts."""
    contacts: List[ContactResponse]
    total: int
