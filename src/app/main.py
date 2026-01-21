"""
FastAPI application main entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.settings import settings
from src.app.api import jobs, issues, staging, contacts
from src.app.logging_config import setup_logging
from src.app.middleware.logging_middleware import LoggingMiddleware

# Setup structured logging (CloudWatch compatible)
setup_logging()

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url="/docs",  # Swagger UI
    redoc_url=None,  # Disable default ReDoc (has CDN issues)
    openapi_url="/openapi.json",  # OpenAPI schema JSON
)

# Add logging middleware (must be before other middleware)
app.add_middleware(LoggingMiddleware)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router)
app.include_router(issues.router)
app.include_router(staging.router)
app.include_router(contacts.router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Data Ingestion API",
        "version": settings.API_VERSION,
    }


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Custom ReDoc endpoint with working CDN URL."""
    html = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>{settings.API_TITLE} - ReDoc</title>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                }}
            </style>
        </head>
        <body>
            <redoc spec-url='/openapi.json'></redoc>
            <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
        </body>
    </html>
    """
    return HTMLResponse(content=html)
