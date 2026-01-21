# Data Ingestion Backend API

FastAPI REST API for the Data Ingestion Tool.

> **Main Documentation**: See [data-ingestion-tool](https://github.com/rpdevelops/data-ingestion-tool) for architecture overview and system flow.

**Live API**: [https://api.rpdevelops.online](https://api.rpdevelops.online)  
**Swagger UI**: [https://api.rpdevelops.online/docs](https://api.rpdevelops.online/docs)

---

## Quick Start

### Prerequisites

- Python 3.11+
- AWS credentials configured
- Environment variables set

### Run Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t data-ingestion-api .
docker run -p 8000:8000 --env-file .env data-ingestion-api
```

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# AWS Cognito
COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_REGION=us-east-1
ALLOWED_GROUP=uploader

# AWS S3
CSV_BUCKET_NAME=my-csv-bucket
AWS_REGION=us-east-1

# AWS SQS
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/queue

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## API Endpoints

### Jobs

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/jobs` | Token | List user's jobs |
| POST | `/jobs/upload` | Token + uploader | Upload CSV file |
| POST | `/jobs/{id}/reprocess` | Token + uploader | Reprocess job |
| DELETE | `/jobs/{id}` | Token + editor | Cancel job |

### Issues

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/issues` | Token | List all user issues |
| GET | `/issues/job/{id}` | Token | List issues for job |
| GET | `/issues/{id}` | Token | Get issue details |
| PUT | `/issues/{id}` | Token + editor | Update issue |

### Staging

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| PUT | `/staging/{id}` | Token + editor | Update staging record |

### Contacts

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/contacts` | Token | List user's contacts |
| GET | `/contacts?email={email}` | Token | Get contact by email |

---

## Upload Endpoint Details

**POST /jobs/upload**

Validates and uploads CSV file for processing.

**Validations**:
- File format: `.csv` extension
- File size: max 5MB
- Content: non-empty with data rows
- Headers: `email`, `first_name`, `last_name`, `company` (case-insensitive)
- Duplicate check: file not previously imported

**Header Variations Supported**:
- email: email, e-mail, e_mail, email_address
- first_name: first_name, firstname, nome, fname
- last_name: last_name, lastname, sobrenome, lname
- company: company, empresa, organization, org

**Response**:
```json
{
  "job_id": 123,
  "message": "File uploaded successfully",
  "filename": "contacts.csv",
  "total_rows": 150
}
```

---

## Authentication

All endpoints require Cognito JWT token in Authorization header:

```
Authorization: Bearer <jwt_token>
```

**User Groups**:
- `uploader`: Can upload files and trigger reprocessing
- `editor`: Can resolve issues, update staging, delete jobs

---

## Project Structure

```
data-ingestion-backend/
├── src/
│   ├── app/
│   │   ├── api/           # Route handlers
│   │   ├── auth/          # Cognito authentication
│   │   ├── repository/    # Data access layer
│   │   ├── db/            # Database connection
│   │   ├── middleware/    # Request logging
│   │   └── main.py        # FastAPI app
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   └── settings.py        # Configuration
├── docs/                  # Additional documentation
├── Dockerfile
└── requirements.txt
```

---

## Logging

Structured JSON logging compatible with CloudWatch:

```json
{
  "timestamp": "2026-01-15T17:41:49.883Z",
  "level": "INFO",
  "message": "Jobs fetched successfully",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "13240852-1021-70eb-a720-347831bb8bec"
}
```

---

## Architectural Decision Records (ADRs)

### ADR-001: FastAPI over Django

**Decision**: Use FastAPI instead of Django REST.

**Rationale**:
- Async-first design
- Automatic OpenAPI documentation
- Pydantic for validation
- Lightweight and fast

---

### ADR-002: Repository Pattern

**Decision**: Abstract database access via repositories.

**Rationale**:
- Separation of concerns
- Easier testing with mocks
- Database-agnostic business logic

---

### ADR-003: Pre-validation Before S3 Upload

**Decision**: Validate CSV before uploading to S3.

**Rationale**:
- Fail fast on invalid files
- No orphaned S3 objects
- Better user feedback

---

### ADR-004: Auto-detect CSV Format

**Decision**: Support multiple encodings and delimiters.

**Rationale**:
- European CSVs often use semicolons
- Excel exports vary by locale
- Better user experience

---

### ADR-005: Structured JSON Logging

**Decision**: Use JSON format for all logs.

**Rationale**:
- CloudWatch Insights queries
- Request tracing via request_id
- Performance metrics

---

## Related Repositories

- [data-ingestion-tool](https://github.com/rpdevelops/data-ingestion-tool) - Main documentation
- [data-ingestion-worker](https://github.com/rpdevelops/data-ingestion-worker) - Async processor
- [data-ingestion-frontend](https://github.com/rpdevelops/data-ingestion-frontend) - Next.js UI
- [data-ingestion-infra](https://github.com/rpdevelops/data-ingestion-infra) - Terraform IaC
