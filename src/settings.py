"""
Application settings and configuration.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str
    
    # AWS Cognito
    COGNITO_USER_POOL_ID: str
    COGNITO_CLIENT_ID: str
    COGNITO_REGION: str = "us-east-1"
    
    # AWS S3
    CSV_BUCKET_NAME: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    
    # AWS SQS
    SQS_QUEUE_URL: Optional[str] = None
    
    # API
    API_TITLE: str = "Data Ingestion API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = """
    FastAPI REST API for the Data Ingestion Tool.
    
    ## Authentication
    All endpoints require AWS Cognito JWT token in the Authorization header:
    ```
    Authorization: Bearer <jwt_token>
    ```
    
    ## User Groups
    - **uploader**: Can upload CSV files and trigger job reprocessing
    - **editor**: Can resolve issues, update staging records, and delete jobs
    
    ## Features
    - CSV file upload with header validation
    - Job processing and tracking
    - Issue management and resolution
    - Contact data management
    - Structured JSON logging for CloudWatch
    
    For more information, visit the [main documentation](https://github.com/rpdevelops/data-ingestion-tool).
    """
    
    # Security
    ALLOWED_GROUP: str = "uploader"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
