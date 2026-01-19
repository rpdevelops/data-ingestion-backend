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

# AWS S3 (required for file uploads)
CSV_BUCKET_NAME=my-csv-bucket
AWS_REGION=us-east-1

# AWS SQS (required for job processing)
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/job-queue

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
- `POST /jobs/upload` - Upload CSV file for processing (requires authentication + "uploader" group)
- `POST /jobs/{job_id}/reprocess` - Reprocess a job by sending message to SQS (requires authentication + "uploader" group)
- `DELETE /jobs/{job_id}` - Cancel/delete a job and all related data (requires authentication + "editor" group)

### Issues

- `GET /issues` - Get all issues for all user's jobs with related staging rows (requires authentication)
- `GET /issues/job/{job_id}` - Get all issues for a specific job with related staging rows (requires authentication)
- `GET /issues/{issue_id}` - Get detailed information about a specific issue with all related staging rows (requires authentication)
- `PUT /issues/{issue_id}` - Update an issue (requires authentication + "editor" group)

### Staging

- `PUT /staging/{staging_id}` - Update a staging record (requires authentication + "editor" group)

### Contacts

- `GET /contacts` - Get all contacts for the authenticated user (requires authentication, filtered by contacts_user_id from token)
- `GET /contacts?email={email}` - Get a specific contact by email address (requires authentication, filtered by contacts_user_id from token)

#### Upload CSV File

**Endpoint**: `POST /jobs/upload`

**Authentication**: Required (JWT token + "uploader" group)

**Request**: 
- Content-Type: `multipart/form-data`
- Body: CSV file (max 5MB)

**Response**:
```json
{
  "job_id": 123,
  "message": "File 'contacts.csv' uploaded successfully and queued for processing",
  "filename": "contacts.csv",
  "total_rows": 150
}
```

**Validations**:
- File must be CSV format (.csv extension)
- File size must be ≤ 5MB
- File must not be empty
- File must have data rows (not just header)
- **CSV must contain required headers**: `email`, `first_name`, `last_name`, `company`
  - Header validation is case-insensitive and supports variations:
    - `email`: email, e-mail, e_mail, email_address
    - `first_name`: first_name, firstname, first name, nome, fname
    - `last_name`: last_name, lastname, last name, sobrenome, lname
    - `company`: company, empresa, organization, org, company_name
  - The validation automatically tries multiple encodings (UTF-8, Latin-1, CP1252, ISO-8859-1, Windows-1252) and delimiters (semicolon, comma, tab) to handle different CSV formats
- File must not have been previously imported (duplicate check)

**Flow**:
1. Validates JWT token and "uploader" group
2. Validates CSV file (format, size, headers, content)
3. Checks for duplicate files
4. Uploads file to S3 (only if all validations pass)
5. Creates job record (status: PENDING)
6. Publishes message to SQS queue (only if all validations pass)
7. Returns job information

**Error Handling**:
- If CSV headers are missing or invalid, the upload is rejected with HTTP 400 before any file is uploaded to S3 or message is sent to SQS
- Error messages include which headers are missing and which headers were found in the file

#### Reprocess Job

**Endpoint**: `POST /jobs/{job_id}/reprocess`

**Authentication**: Required (JWT token + "uploader" group)

**Response**:
```json
{
  "job_id": 123,
  "message": "Job 123 queued for reprocessing",
  "s3_key": "uploads/user-id-123/contacts.csv"
}
```

**Features**:
- Sends the same message format to SQS that is sent during CSV upload
- Verifies that the job belongs to the authenticated user
- Uses the existing S3 key from the job record
- Returns 404 if job not found or user doesn't have access
- Returns 503 if SQS message publishing fails
- Allows reprocessing of existing jobs without re-uploading the CSV file

#### Cancel/Delete Job

**Endpoint**: `DELETE /jobs/{job_id}`

**Authentication**: Required (JWT token + "editor" group)

**Response**:
```json
{
  "message": "Job 123 cancelled successfully",
  "job_id": 123
}
```

**Features**:
- Only jobs with status PENDING, NEEDS_REVIEW, or FAILED can be cancelled
- Deletes all related data via CASCADE:
  - All staging records related to the job
  - All issue_items related to the job
  - All issues related to the job
- Deletes the job record from database
- Deletes the CSV file from S3 bucket
- Verifies that the job belongs to the authenticated user
- Returns 404 if job not found or user doesn't have access
- Returns 400 if job status doesn't allow deletion (PROCESSING or COMPLETED)
- Returns 403 if user doesn't belong to "editor" group

#### Get All User Issues

**Endpoint**: `GET /issues`

**Authentication**: Required (JWT token only, no group required)

**Response**:
```json
{
  "issues": [
    {
      "issue_id": 1,
      "issues_job_id": 5,
      "issue_type": "DUPLICATE_EMAIL",
      "issue_resolved": false,
      "issue_description": "Email appears multiple times with different identities",
      "issue_resolved_at": null,
      "issue_resolved_by": null,
      "issue_resolution_comment": null,
      "issue_created_at": "2026-01-15T21:50:07Z",
      "affected_rows": [
        {
          "staging_id": 123,
          "staging_email": "test@example.com",
          "staging_first_name": "John",
          "staging_last_name": "Doe",
          "staging_company": "Company A",
          "staging_created_at": "2026-01-15T21:50:07Z",
          "staging_status": "ISSUE"
        }
      ]
    }
  ],
  "total": 1,
  "resolved_count": 0,
  "unresolved_count": 1
}
```

**Features**:
- Returns all issues from all jobs belonging to the authenticated user
- Returns issues with related staging rows (join via issue_items)
- Excludes `staging_row_hash` and `issue_key` (used only for idempotency)
- Includes counts: total, resolved, and unresolved issues across all user's jobs
- Issues are ordered by creation date (newest first)

#### Get Job Issues

**Endpoint**: `GET /issues/job/{job_id}`

**Authentication**: Required (JWT token only, no group required)

**Response**:
```json
{
  "issues": [
    {
      "issue_id": 1,
      "issues_job_id": 5,
      "issue_type": "DUPLICATE_EMAIL",
      "issue_resolved": false,
      "issue_description": "Email appears multiple times with different identities",
      "issue_resolved_at": null,
      "issue_resolved_by": null,
      "issue_resolution_comment": null,
      "issue_created_at": "2026-01-15T21:50:07Z",
      "affected_rows": [
        {
          "staging_id": 123,
          "staging_email": "test@example.com",
          "staging_first_name": "John",
          "staging_last_name": "Doe",
          "staging_company": "Company A",
          "staging_created_at": "2026-01-15T21:50:07Z",
          "staging_status": "ISSUE"
        }
      ]
    }
  ],
  "total": 1,
  "resolved_count": 0,
  "unresolved_count": 1
}
```

**Features**:
- Returns issues with related staging rows (join via issue_items)
- Excludes `staging_row_hash` and `issue_key` (used only for idempotency)
- Includes counts: total, resolved, and unresolved issues
- Only returns issues for jobs owned by the authenticated user

#### Get Issue Details

**Endpoint**: `GET /issues/{issue_id}`

**Authentication**: Required (JWT token only, no group required)

**Response**:
```json
{
  "issue_id": 1,
  "issues_job_id": 5,
  "issue_type": "DUPLICATE_EMAIL",
  "issue_resolved": false,
  "issue_description": "Email appears multiple times with different identities",
  "issue_resolved_at": null,
  "issue_resolved_by": null,
  "issue_resolution_comment": null,
  "issue_created_at": "2026-01-15T21:50:07Z",
  "affected_rows": [
    {
      "staging_id": 123,
      "staging_email": "test@example.com",
      "staging_first_name": "John",
      "staging_last_name": "Doe",
      "staging_company": "Company A",
      "staging_created_at": "2026-01-15T21:50:07Z",
      "staging_status": "ISSUE"
    },
    {
      "staging_id": 124,
      "staging_email": "test@example.com",
      "staging_first_name": "Jane",
      "staging_last_name": "Smith",
      "staging_company": "Company B",
      "staging_created_at": "2026-01-15T21:50:08Z",
      "staging_status": "ISSUE"
    }
  ]
}
```

**Features**:
- Returns complete issue information (all fields except `issue_key`)
- Returns all related staging rows (complete records except `staging_row_hash`)
- Verifies that the issue belongs to a job owned by the authenticated user
- Returns 404 if issue not found or user doesn't have access

#### Update Issue

**Endpoint**: `PUT /issues/{issue_id}`

**Authentication**: Required (JWT token + "editor" group)

**Request Body**:
```json
{
  "issue_resolved": true,
  "issue_description": "Updated description",
  "issue_resolved_by": "user-id-123",
  "issue_resolution_comment": "Issue resolved after manual review"
}
```

**Response**:
```json
{
  "issue_id": 1,
  "issues_job_id": 5,
  "issue_type": "DUPLICATE_EMAIL",
  "issue_resolved": true,
  "issue_description": "Updated description",
  "issue_resolved_at": "2026-01-15T22:00:00Z",
  "issue_resolved_by": "user-id-123",
  "issue_resolution_comment": "Issue resolved after manual review",
  "issue_created_at": "2026-01-15T21:50:07Z",
  "affected_rows": [...]
}
```

**Features**:
- Updates only the fields provided in the request body
- Fields not included in the request remain unchanged
- When resolving an issue (`issue_resolved=true`):
  - `issue_resolved_at` is automatically set to current timestamp if not already set
  - If `issue_resolved_by` is not provided, it defaults to the authenticated user's ID
- When unresolving an issue (`issue_resolved=false`):
  - `issue_resolved_at` and `issue_resolved_by` are automatically cleared
- Verifies that the issue belongs to a job owned by the authenticated user
- Returns 404 if issue not found or user doesn't have access
- Returns 403 if user doesn't belong to "editor" group
- Returns updated issue with all related staging rows (excluding `staging_row_hash` and `issue_key`)

## Staging

### Update Staging Record

**Endpoint**: `PUT /staging/{staging_id}`

**Authentication**: Required (JWT token + "editor" group)

**Request Body**:
```json
{
  "staging_email": "updated@example.com",
  "staging_first_name": "John",
  "staging_last_name": "Doe",
  "staging_company": "Updated Company",
  "staging_status": "READY"
}
```

**Response**:
```json
{
  "staging_id": 123,
  "staging_job_id": 5,
  "staging_email": "updated@example.com",
  "staging_first_name": "John",
  "staging_last_name": "Doe",
  "staging_company": "Updated Company",
  "staging_created_at": "2026-01-15T21:50:07Z",
  "staging_status": "READY"
}
```

**Features**:
- Updates only the fields provided in the request body
- Fields not included in the request remain unchanged
- Verifies that the staging belongs to a job owned by the authenticated user
- Returns 404 if staging not found or user doesn't have access
- Returns updated staging record (excluding `staging_row_hash`)
- All fields are optional in the request (partial updates supported)

## Contacts

### Get All Contacts

**Endpoint**: `GET /contacts`

**Authentication**: Required (JWT token only, no group required)

**Response**:
```json
{
  "contacts": [
    {
      "contact_id": 1,
      "staging_id": 123,
      "contacts_user_id": "13240852-1021-70eb-a720-347831bb8bec",
      "contact_email": "john.doe@example.com",
      "contact_first_name": "John",
      "contact_last_name": "Doe",
      "contact_company": "Company A",
      "contact_created_at": "2026-01-15T21:50:07Z"
    }
  ],
  "total": 1
}
```

**Features**:
- Returns all contacts for the authenticated user (filtered by contacts_user_id from JWT token)
- Contacts are ordered by creation date (newest first)
- Filters directly on contacts_user_id field (no joins needed)
- Automatically uses user_id from JWT token

### Get Contact by Email

**Endpoint**: `GET /contacts?email={email}`

**Authentication**: Required (JWT token only, no group required)

**Query Parameters**:
- `email` (optional): Email address to search for

**Response** (when email is provided):
```json
{
  "contacts": [
    {
      "contact_id": 1,
      "staging_id": 123,
      "contacts_user_id": "13240852-1021-70eb-a720-347831bb8bec",
      "contact_email": "john.doe@example.com",
      "contact_first_name": "John",
      "contact_last_name": "Doe",
      "contact_company": "Company A",
      "contact_created_at": "2026-01-15T21:50:07Z"
    }
  ],
  "total": 1
}
```

**Features**:
- If email parameter is provided, returns only the contact matching that email
- If email parameter is not provided, returns all contacts (same as GET /contacts)
- Filters by contacts_user_id from JWT token (no joins needed)
- Returns 404 if contact with email not found or user doesn't have access

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
