# Data Ingestion Backend API

FastAPI backend for the Data Ingestion Tool.

## Architecture

This backend follows clean architecture principles with clear separation of concerns:

- **API Layer** (`src/app/api/`): FastAPI route handlers
- **Auth Layer** (`src/app/auth/`): AWS Cognito authentication and authorization
- **Repository Layer** (`src/app/repository/`): Data access abstraction
- **Models** (`src/models/`): SQLAlchemy database models
- **Schemas** (`src/schemas/`): Pydantic request/response schemas
- **Database** (`src/app/db/`): Database connection and session management
- **Logging** (`src/app/logging_config.py`): Structured JSON logging for CloudWatch
- **Middleware** (`src/app/middleware/`): Request/response logging middleware

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL database (AWS RDS)
- AWS Cognito User Pool configured
- Environment variables configured

### Environment Variables

Create a `.env` file in the root directory:

```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_REGION=us-east-1
ALLOWED_GROUP=uploader

# Logging (optional)
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json         # json (for CloudWatch) or simple (for local dev)
```

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running Locally

```bash
uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Jobs

- `GET /jobs` - Get all jobs (requires authentication, returns user's jobs by default)

## Authentication

All API endpoints require AWS Cognito JWT authentication. The token must be provided in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

### How Authentication Works

Authentication is applied using FastAPI's `Depends()` mechanism:

- **Authentication only**: `Depends(get_current_user)` - Requires valid JWT token
- **Authentication + Group**: `Depends(require_group("uploader"))` - Requires token AND group membership

### Quick Examples

**Endpoint with authentication only:**
```python
@router.get("/jobs")
def get_jobs(current_user: dict = Depends(get_current_user)):
    # Any authenticated user can access
    pass
```

**Endpoint requiring "uploader" group:**
```python
@router.post("/upload")
def upload(current_user: dict = Depends(require_group("uploader"))):
    # Only users in "uploader" group can access
    pass
```

## Logging

The application uses structured JSON logging that is compatible with AWS CloudWatch Logs.

### Features

- **Structured JSON logs**: All logs are formatted as JSON for easy parsing and querying in CloudWatch
- **Request tracing**: Each request gets a unique `request_id` for end-to-end traceability
- **Contextual logging**: Logs include relevant context (user_id, job_id, request_id, etc.)
- **Performance metrics**: Request duration is automatically logged
- **Error tracking**: Exceptions are logged with full stack traces

### Log Format

In production (CloudWatch), logs are formatted as JSON:
```json
{
  "timestamp": "2026-01-15T17:41:49.883Z",
  "level": "INFO",
  "logger": "src.app.api.jobs",
  "message": "Jobs fetched successfully",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "13240852-1021-70eb-a720-347831bb8bec",
  "job_count": 1
}
```

For local development, you can use simple format by setting `LOG_FORMAT=simple`.

### Environment Variables

- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
- `LOG_FORMAT`: Log format (json or simple). Default: json

### CloudWatch Integration

When deployed to ECS Fargate, logs are automatically sent to CloudWatch Logs. The structured JSON format allows you to:

- Query logs by specific fields (e.g., `user_id`, `request_id`)
- Create CloudWatch Insights queries
- Set up alarms based on log patterns
- Track request performance and errors

Example CloudWatch Insights query:
```
fields @timestamp, level, message, request_id, user_id, duration_ms
| filter level = "ERROR"
| sort @timestamp desc
```

## Docker

Build and run with Docker:

```bash
docker build -t data-ingestion-api .
docker run -p 8000:8000 --env-file .env data-ingestion-api
```

When running in ECS Fargate, ensure the task has the appropriate IAM role to write to CloudWatch Logs.
