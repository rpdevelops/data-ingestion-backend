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
    API_DESCRIPTION: str = "Data Ingestion Tool API"
    
    # Security
    ALLOWED_GROUP: str = "uploader"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
