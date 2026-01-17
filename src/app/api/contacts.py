"""
Contacts API endpoints.

Authentication and Authorization:
- All endpoints require authentication via JWT token (Depends(get_current_user))
- No group required (any authenticated user can access their own contacts)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional

from src.app.db.database import get_db
from src.app.auth.cognito_auth import get_current_user
from src.app.repository.contact_repository import ContactRepository
from src.schemas.contact import ContactListResponse, ContactResponse
from src.app.logging_config import get_logger

logger = get_logger(__name__)


router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get(
    "",
    response_model=ContactListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all contacts or search by email",
    description="""
    Get all contacts for the authenticated user, or search for a specific contact by email.
    
    **Authentication**: Required (JWT token)
    **Authorization**: No group required (any authenticated user can access their own contacts)
    
    If email parameter is provided, returns only the contact matching that email.
    If email parameter is not provided, returns all contacts for the user (filtered by contacts_user_id).
    Contacts are ordered by creation date (newest first).
    """
)
def get_contacts(
    request: Request,
    email: Optional[str] = Query(None, description="Email address to search for"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ← AUTHENTICATION: Requires valid JWT token
):
    """
    Get contacts for the authenticated user.
    
    If email is provided, returns only the contact matching that email.
    If email is not provided, returns all contacts for the user (filtered by contacts_user_id).
    
    Args:
        request: FastAPI request object (for request_id)
        email: Optional email address to search for
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        ContactListResponse with contacts and total count
        
    Raises:
        HTTPException 404: If contact with email not found (when email is provided)
        HTTPException 401: If authentication fails
    """
    request_id = getattr(request.state, "request_id", None)
    user_id = current_user["user_id"]
    
    if email:
        # Search for specific contact by email
        logger.info(
            "Searching contact by email",
            extra={
                "request_id": request_id,
                "email": email,
                "user_id": user_id,
            }
        )
        
        contact = ContactRepository.get_contact_by_email(db, email, user_id, request_id)
        
        if not contact:
            logger.warning(
                "Contact not found by email",
                extra={
                    "request_id": request_id,
                    "email": email,
                    "user_id": user_id,
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contact with email '{email}' not found or you don't have access to it"
            )
        
        # Create response
        contact_response = ContactResponse(
            contact_id=contact.contact_id,
            staging_id=contact.staging_id,
            contacts_user_id=contact.contacts_user_id,
            contact_email=contact.contact_email,
            contact_first_name=contact.contact_first_name,
            contact_last_name=contact.contact_last_name,
            contact_company=contact.contact_company,
            contact_created_at=contact.contact_created_at,
        )
        
        logger.info(
            "Contact found by email",
            extra={
                "request_id": request_id,
                "email": email,
                "user_id": user_id,
                "contact_id": contact.contact_id,
            }
        )
        
        return ContactListResponse(
            contacts=[contact_response],
            total=1,
        )
    else:
        # Get all contacts
        logger.info(
            "Fetching all contacts for user",
            extra={
                "request_id": request_id,
                "user_id": user_id,
            }
        )
        
        contacts = ContactRepository.get_all_contacts_by_user_id(db, user_id, request_id)
        
        # Build response
        contact_responses = [
            ContactResponse(
                contact_id=contact.contact_id,
                staging_id=contact.staging_id,
                contacts_user_id=contact.contacts_user_id,
                contact_email=contact.contact_email,
                contact_first_name=contact.contact_first_name,
                contact_last_name=contact.contact_last_name,
                contact_company=contact.contact_company,
                contact_created_at=contact.contact_created_at,
            )
            for contact in contacts
        ]
        
        logger.info(
            "All contacts fetched successfully",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "total_contacts": len(contact_responses),
            }
        )
        
        return ContactListResponse(
            contacts=contact_responses,
            total=len(contact_responses),
        )
