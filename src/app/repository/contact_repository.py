"""
Repository for contact data access operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models.contact import Contact
from src.app.logging_config import get_logger

logger = get_logger(__name__)


class ContactRepository:
    """Repository for contact operations."""
    
    @staticmethod
    def get_all_contacts_by_user_id(
        db: Session,
        user_id: str,
        request_id: Optional[str] = None
    ) -> List[Contact]:
        """
        Get all contacts for a specific user by filtering directly on contacts_user_id.
        
        Args:
            db: Database session
            user_id: User ID to filter contacts
            request_id: Request ID for logging traceability
            
        Returns:
            List of Contact objects, ordered by creation date (newest first)
        """
        # Filter contacts directly by contacts_user_id (no join needed)
        contacts = (
            db.query(Contact)
            .filter(Contact.contacts_user_id == user_id)
            .order_by(desc(Contact.contact_created_at))
            .all()
        )
        
        logger.debug(
            "All contacts query completed for user",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "contact_count": len(contacts),
            }
        )
        
        return contacts
    
    @staticmethod
    def get_contact_by_email(
        db: Session,
        email: str,
        user_id: str,
        request_id: Optional[str] = None
    ) -> Optional[Contact]:
        """
        Get a contact by email address.
        Verifies that the contact belongs to the user by filtering on contacts_user_id.
        
        Args:
            db: Database session
            email: Email address to search for
            user_id: User ID to verify ownership
            request_id: Request ID for logging traceability
            
        Returns:
            Contact object, or None if not found or access denied
        """
        # Get contact by email, filtering directly on contacts_user_id (no join needed)
        contact = (
            db.query(Contact)
            .filter(
                Contact.contact_email == email,
                Contact.contacts_user_id == user_id
            )
            .first()
        )
        
        if not contact:
            logger.warning(
                "Contact not found or access denied",
                extra={
                    "request_id": request_id,
                    "email": email,
                    "user_id": user_id,
                }
            )
            return None
        
        logger.debug(
            "Contact query completed",
            extra={
                "request_id": request_id,
                "email": email,
                "user_id": user_id,
                "contact_id": contact.contact_id,
            }
        )
        
        return contact
