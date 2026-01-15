"""
SQS service for publishing job messages.
"""
import json
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from src.settings import settings
from src.app.logging_config import get_logger

logger = get_logger(__name__)


class SQSService:
    """Service for SQS operations."""
    
    def __init__(self):
        """Initialize SQS client."""
        self.queue_url = settings.SQS_QUEUE_URL
        
        # Extract region from queue URL if available, otherwise use AWS_REGION setting
        # Queue URL format: https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}
        if self.queue_url:
            try:
                # Extract region from queue URL using regex
                # Example: https://sqs.eu-central-1.amazonaws.com/123456789012/queue-name
                import re
                match = re.search(r'https://sqs\.([^.]+)\.amazonaws\.com', self.queue_url)
                if match:
                    self.region = match.group(1)  # eu-central-1
                    logger.debug(
                        "Extracted region from SQS queue URL",
                        extra={
                            "queue_url": self.queue_url,
                            "extracted_region": self.region,
                        }
                    )
                else:
                    self.region = settings.AWS_REGION
                    logger.warning(
                        "Could not extract region from SQS queue URL, using AWS_REGION setting",
                        extra={
                            "queue_url": self.queue_url,
                            "fallback_region": self.region,
                        }
                    )
            except Exception as e:
                self.region = settings.AWS_REGION
                logger.warning(
                    "Error extracting region from SQS queue URL, using AWS_REGION setting",
                    extra={
                        "queue_url": self.queue_url,
                        "fallback_region": self.region,
                        "error": str(e),
                    }
                )
        else:
            self.region = settings.AWS_REGION
        
        # Initialize SQS client
        # boto3 will automatically use credentials from:
        # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        # 2. ~/.aws/credentials file
        # 3. IAM role (when running on EC2/ECS)
        try:
            self.sqs_client = boto3.client('sqs', region_name=self.region)
            
            # Log AWS credentials status (without exposing secrets)
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials:
                logger.debug(
                    "AWS credentials found",
                    extra={
                        "access_key_id": credentials.access_key[:4] + "..." if credentials.access_key else None,
                        "region": self.region,
                    }
                )
            else:
                logger.warning(
                    "No AWS credentials found. boto3 will try to use IAM role or default profile.",
                    extra={"region": self.region}
                )
        except Exception as e:
            logger.error(
                "Failed to initialize SQS client",
                extra={
                    "region": self.region,
                    "error": str(e),
                },
                exc_info=True
            )
            raise
    
    def publish_job_message(self, job_id: int, s3_key: str) -> None:
        """
        Publish a job processing message to SQS queue.
        
        Args:
            job_id: Job ID
            s3_key: S3 object key for the CSV file
            
        Raises:
            Exception: If message publishing fails
        """
        if not self.queue_url:
            logger.warning(
                "SQS_QUEUE_URL not configured, skipping message publish",
                extra={"job_id": job_id, "s3_key": s3_key}
            )
            return
        
        message_body = {
            "job_id": job_id,
            "s3_key": s3_key
        }
        
        try:
            logger.info(
                "Publishing job message to SQS",
                extra={
                    "queue_url": self.queue_url,
                    "job_id": job_id,
                    "s3_key": s3_key,
                }
            )
            
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
            )
            
            message_id = response.get('MessageId')
            logger.info(
                "Job message published successfully",
                extra={
                    "queue_url": self.queue_url,
                    "job_id": job_id,
                    "message_id": message_id,
                }
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            # Handle specific error: Queue does not exist OR access denied
            # AWS returns "NonExistentQueue" for both cases (queue doesn't exist OR no permission)
            if error_code == 'AWS.SimpleQueueService.NonExistentQueue':
                # Check if it might be a permissions issue
                logger.error(
                    "SQS queue access failed",
                    extra={
                        "queue_url": self.queue_url,
                        "job_id": job_id,
                        "error_code": error_code,
                        "error_message": error_message,
                        "region": self.region,
                        "note": "This error can occur if: 1) Queue doesn't exist, OR 2) No access policy/permissions configured",
                    },
                    exc_info=True
                )
                raise Exception(
                    f"SQS queue access failed: {self.queue_url}. "
                    f"Possible causes: 1) Queue doesn't exist, OR 2) No access policy configured on the queue, "
                    f"OR 3) AWS credentials don't have permission. "
                    f"Please verify: queue exists, access policy allows SendMessage, and AWS credentials are configured."
                )
            
            logger.error(
                "SQS publish failed",
                extra={
                    "queue_url": self.queue_url,
                    "job_id": job_id,
                    "error_code": error_code,
                    "error": str(e),
                },
                exc_info=True
            )
            raise Exception(f"Failed to publish message to SQS: {error_code}")
        
        except BotoCoreError as e:
            logger.error(
                "SQS client error",
                extra={
                    "queue_url": self.queue_url,
                    "error": str(e),
                },
                exc_info=True
            )
            raise Exception(f"SQS service error: {str(e)}")
        
        except Exception as e:
            logger.error(
                "Unexpected error during SQS publish",
                extra={
                    "queue_url": self.queue_url,
                    "job_id": job_id,
                    "error": str(e),
                },
                exc_info=True
            )
            raise


# Singleton instance
sqs_service = SQSService()
