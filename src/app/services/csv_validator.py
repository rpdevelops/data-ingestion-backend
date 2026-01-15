"""
CSV file validation service.
"""
import csv
import io
import hashlib
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException, status

from src.app.logging_config import get_logger

logger = get_logger(__name__)

# Maximum file size: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes


class CSVValidationError(Exception):
    """Custom exception for CSV validation errors."""
    pass


class CSVValidator:
    """Service for validating CSV files."""
    
    @staticmethod
    def validate_file_size(file_size: int) -> None:
        """
        Validate that file size is within limits.
        
        Args:
            file_size: File size in bytes
            
        Raises:
            CSVValidationError: If file is too large
        """
        if file_size > MAX_FILE_SIZE:
            raise CSVValidationError(
                f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size (5MB)"
            )
        
        if file_size == 0:
            raise CSVValidationError("File is empty")
    
    @staticmethod
    def validate_file_format(filename: str) -> None:
        """
        Validate that file has CSV extension.
        
        Args:
            filename: Original filename
            
        Raises:
            CSVValidationError: If file format is invalid
        """
        if not filename.lower().endswith('.csv'):
            raise CSVValidationError("File must be a CSV file (.csv extension required)")
    
    @staticmethod
    def validate_csv_content(file_content: bytes) -> Tuple[int, str]:
        """
        Validate CSV content and count rows.
        
        Args:
            file_content: CSV file content as bytes
            
        Returns:
            Tuple of (row_count, file_hash)
            
        Raises:
            CSVValidationError: If CSV is invalid or empty
        """
        try:
            # Decode file content
            try:
                content_str = file_content.decode('utf-8')
            except UnicodeDecodeError:
                # Try other common encodings
                try:
                    content_str = file_content.decode('latin-1')
                except UnicodeDecodeError:
                    raise CSVValidationError("File encoding is not supported. Please use UTF-8 or Latin-1.")
            
            # Check if file is empty
            if not content_str.strip():
                raise CSVValidationError("CSV file is empty")
            
            # Parse CSV
            csv_reader = csv.reader(io.StringIO(content_str))
            rows = list(csv_reader)
            
            # Check if CSV has at least a header row
            if len(rows) == 0:
                raise CSVValidationError("CSV file has no rows")
            
            # Count data rows (excluding header)
            data_rows = len(rows) - 1
            
            if data_rows == 0:
                raise CSVValidationError("CSV file has no data rows (only header)")
            
            # Generate file hash for duplicate detection
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            logger.debug(
                "CSV content validated",
                extra={
                    "total_rows": len(rows),
                    "data_rows": data_rows,
                    "file_hash": file_hash[:16] + "...",  # Log only first 16 chars
                }
            )
            
            return data_rows, file_hash
            
        except csv.Error as e:
            raise CSVValidationError(f"Invalid CSV format: {str(e)}")
        except Exception as e:
            if isinstance(e, CSVValidationError):
                raise
            raise CSVValidationError(f"Error reading CSV file: {str(e)}")
    
    @staticmethod
    async def validate_upload_file(file: UploadFile) -> Tuple[bytes, int, str]:
        """
        Validate uploaded CSV file.
        
        This method performs all validations:
        1. File format (must be .csv)
        2. File size (max 5MB, not empty)
        3. CSV content (valid format, not empty, has data rows)
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            Tuple of (file_content, row_count, file_hash)
            
        Raises:
            HTTPException: If validation fails
        """
        try:
            # Validate filename
            CSVValidator.validate_file_format(file.filename)
            
            # Read file content
            file_content = await file.read()
            
            # Validate file size
            CSVValidator.validate_file_size(len(file_content))
            
            # Validate CSV content
            row_count, file_hash = CSVValidator.validate_csv_content(file_content)
            
            logger.info(
                "CSV file validation passed",
                extra={
                    "file_name": file.filename,
                    "file_size": len(file_content),
                    "row_count": row_count,
                }
            )
            
            return file_content, row_count, file_hash
            
        except CSVValidationError as e:
            logger.warning(
                "CSV validation failed",
                extra={
                    "file_name": file.filename,
                    "error": str(e),
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(
                "Unexpected error during CSV validation",
                extra={
                    "file_name": file.filename,
                    "error": str(e),
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error validating file: {str(e)}"
            )


# Singleton instance
csv_validator = CSVValidator()
