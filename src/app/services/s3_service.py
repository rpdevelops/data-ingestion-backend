"""
S3 service for uploading CSV files.
"""
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from typing import BinaryIO
import uuid
from datetime import datetime

from src.settings import settings
from src.app.logging_config import get_logger

logger = get_logger(__name__)


class S3Service:
    """Service for S3 operations."""
    
    def __init__(self):
        """Initialize S3 client."""
        self.bucket_name = settings.CSV_BUCKET_NAME
        self.region = settings.AWS_REGION
        self.s3_client = boto3.client('s3', region_name=self.region)
    
    def upload_csv_file(
        self,
        file_content: bytes,
        original_filename: str,
        user_id: str
    ) -> str:
        """
        Upload CSV file to S3 bucket.
        
        Args:
            file_content: File content as bytes
            original_filename: Original filename from user
            user_id: User ID for organizing files
            
        Returns:
            S3 object key (path in bucket)
            
        Raises:
            Exception: If upload fails
        """
        if not self.bucket_name:
            raise ValueError("CSV_BUCKET_NAME is not configured")
        
        # Generate unique S3 key: uploads/{user_id}/{timestamp}-{uuid}-{filename}
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = original_filename.replace(" ", "_").replace("/", "_")
        s3_key = f"uploads/{user_id}/{timestamp}-{unique_id}-{safe_filename}"
        
        try:
            logger.info(
                "Uploading file to S3",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                    "file_name": original_filename,
                    "file_size": len(file_content),
                }
            )
            
            # Upload file to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType='text/csv',
                ServerSideEncryption='AES256',
            )
            
            logger.info(
                "File uploaded successfully",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                }
            )
            
            return s3_key
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(
                "S3 upload failed",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                    "error_code": error_code,
                    "error": str(e),
                },
                exc_info=True
            )
            raise Exception(f"Failed to upload file to S3: {error_code}")
        
        except BotoCoreError as e:
            logger.error(
                "S3 client error",
                extra={
                    "bucket": self.bucket_name,
                    "error": str(e),
                },
                exc_info=True
            )
            raise Exception(f"S3 service error: {str(e)}")
        
        except Exception as e:
            logger.error(
                "Unexpected error during S3 upload",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                    "error": str(e),
                },
                exc_info=True
            )
            raise
    
    def delete_file(self, s3_key: str) -> None:
        """
        Delete a file from S3 bucket.
        
        Args:
            s3_key: S3 object key to delete
            
        Raises:
            Exception: If deletion fails
        """
        if not self.bucket_name:
            raise ValueError("CSV_BUCKET_NAME is not configured")
        
        try:
            logger.info(
                "Deleting file from S3",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                }
            )
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            
            logger.info(
                "File deleted successfully from S3",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                }
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(
                "S3 delete failed",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                    "error_code": error_code,
                    "error": str(e),
                },
                exc_info=True
            )
            raise Exception(f"Failed to delete file from S3: {error_code}")
        
        except BotoCoreError as e:
            logger.error(
                "S3 client error during delete",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                    "error": str(e),
                },
                exc_info=True
            )
            raise Exception(f"S3 service error during delete: {str(e)}")
        
        except Exception as e:
            logger.error(
                "Unexpected error during S3 delete",
                extra={
                    "bucket": self.bucket_name,
                    "s3_key": s3_key,
                    "error": str(e),
                },
                exc_info=True
            )
            raise


# Singleton instance
s3_service = S3Service()
