"""
CSV file validation service.
"""
import csv
import io
import hashlib
from typing import Tuple, Optional, List, Dict
from fastapi import UploadFile, HTTPException, status

from src.app.logging_config import get_logger

logger = get_logger(__name__)

# Maximum file size: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

# Required CSV headers (case-insensitive, with variations)
REQUIRED_HEADERS = {
    'email': ['email', 'e-mail', 'e_mail', 'email_address'],
    'first_name': ['first_name', 'firstname', 'first name', 'nome', 'fname'],
    'last_name': ['last_name', 'lastname', 'last name', 'sobrenome', 'lname'],
    'company': ['company', 'empresa', 'organization', 'org', 'company_name']
}


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
    def _normalize_header(header: str) -> str:
        """
        Normalize header name for comparison (lowercase, strip whitespace).
        
        Args:
            header: Header name to normalize
            
        Returns:
            Normalized header name
        """
        return header.strip().lower() if header else ""
    
    @staticmethod
    def _find_required_header(header_name: str, csv_headers: List[str]) -> Optional[str]:
        """
        Find a required header in CSV headers, checking for variations.
        
        Args:
            header_name: Required header name (key from REQUIRED_HEADERS)
            csv_headers: List of CSV header names
            
        Returns:
            Found header name from CSV, or None if not found
        """
        variations = REQUIRED_HEADERS.get(header_name, [])
        normalized_csv_headers = {CSVValidator._normalize_header(h): h for h in csv_headers}
        
        # Check each variation
        for variation in variations:
            normalized_variation = CSVValidator._normalize_header(variation)
            if normalized_variation in normalized_csv_headers:
                return normalized_csv_headers[normalized_variation]
        
        return None
    
    @staticmethod
    def validate_csv_headers(file_content: bytes) -> None:
        """
        Validate that CSV file contains required headers.
        Tries multiple encodings and delimiters (same logic as worker's read_csv_file).
        
        Args:
            file_content: CSV file content as bytes
            
        Raises:
            CSVValidationError: If required headers are missing
        """
        # Try multiple encodings in order of preference (same as worker)
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1", "windows-1252"]
        content = None
        used_encoding = None
        
        for encoding in encodings:
            try:
                content = file_content.decode(encoding)
                used_encoding = encoding
                logger.debug(
                    "CSV decoded successfully with encoding for header validation",
                    extra={"encoding": encoding}
                )
                break
            except UnicodeDecodeError:
                logger.debug(
                    "Failed to decode CSV with encoding, trying next",
                    extra={"encoding": encoding}
                )
                continue
        
        if content is None:
            raise CSVValidationError(
                f"Failed to decode CSV file with any encoding. "
                f"Tried: {', '.join(encodings)}"
            )
        
        # Try different delimiters (same as worker: semicolon first for European format)
        delimiters = [';', ',', '\t']
        headers = None
        used_delimiter = None
        
        for delimiter in delimiters:
            try:
                content_io = io.StringIO(content)
                csv_reader = csv.DictReader(content_io, delimiter=delimiter)
                
                # Get fieldnames
                if csv_reader.fieldnames:
                    # Clean headers (strip whitespace, remove empty)
                    cleaned_headers = [
                        h.strip() for h in csv_reader.fieldnames 
                        if h and h.strip()
                    ]
                    
                    # Check if we got meaningful headers
                    if cleaned_headers and len(cleaned_headers) > 1:
                        # Verify field names look reasonable (same logic as worker)
                        if delimiter == ';':
                            field_names_look_valid = not any(',' in str(fn) for fn in cleaned_headers if fn)
                        elif delimiter == ',':
                            field_names_look_valid = not any(';' in str(fn) for fn in cleaned_headers if fn)
                        else:
                            field_names_look_valid = not any(',' in str(fn) or ';' in str(fn) for fn in cleaned_headers if fn)
                        
                        if field_names_look_valid:
                            headers = cleaned_headers
                            used_delimiter = delimiter
                            logger.debug(
                                "CSV headers detected successfully",
                                extra={
                                    "delimiter": repr(delimiter),
                                    "headers": headers,
                                    "encoding": used_encoding
                                }
                            )
                            break
            except Exception as e:
                logger.debug(
                    "Failed to parse CSV headers with delimiter, trying next",
                    extra={
                        "delimiter": repr(delimiter),
                        "error": str(e)
                    }
                )
                continue
        
        # If no delimiter worked, try default (comma)
        if headers is None:
            logger.debug(
                "Could not parse CSV headers with common delimiters, using default comma",
                extra={"delimiters_tried": [repr(d) for d in delimiters]}
            )
            csv_reader = csv.DictReader(io.StringIO(content))
            if csv_reader.fieldnames:
                headers = [h.strip() for h in csv_reader.fieldnames if h and h.strip()]
                used_delimiter = ','
        
        if not headers:
            raise CSVValidationError(
                "Could not detect CSV headers. Please ensure the file has a header row."
            )
        
        # Validate required headers
        missing_headers = []
        found_headers = {}
        
        for required_key, variations in REQUIRED_HEADERS.items():
            found_header = CSVValidator._find_required_header(required_key, headers)
            if found_header:
                found_headers[required_key] = found_header
            else:
                missing_headers.append(required_key)
        
        if missing_headers:
            # Create user-friendly error message
            missing_names = {
                'email': 'email',
                'first_name': 'first_name',
                'last_name': 'last_name',
                'company': 'company'
            }
            missing_display = [missing_names.get(h, h) for h in missing_headers]
            
            logger.warning(
                "CSV header validation failed - missing required headers",
                extra={
                    "missing_headers": missing_headers,
                    "found_headers": list(headers),
                    "encoding": used_encoding,
                    "delimiter": used_delimiter
                }
            )
            
            raise CSVValidationError(
                f"CSV file is missing required headers: {', '.join(missing_display)}. "
                f"Found headers: {', '.join(headers)}. "
                f"Please ensure your CSV file contains columns for: email, first_name, last_name, and company."
            )
        
        logger.info(
            "CSV header validation passed",
            extra={
                "found_headers": found_headers,
                "all_headers": headers,
                "encoding": used_encoding,
                "delimiter": used_delimiter
            }
        )
    
    @staticmethod
    async def validate_upload_file(file: UploadFile) -> Tuple[bytes, int, str]:
        """
        Validate uploaded CSV file.
        
        This method performs all validations:
        1. File format (must be .csv)
        2. File size (max 5MB, not empty)
        3. CSV content (valid format, not empty, has data rows)
        4. CSV headers (required headers: email, first_name, last_name, company)
        
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
            
            # Validate CSV headers (BEFORE validating content)
            # This uses the same encoding/delimiter logic as the worker
            CSVValidator.validate_csv_headers(file_content)
            
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
