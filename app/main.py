import json
import logging
from contextlib import asynccontextmanager

import redis
import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import settings
from .db.session import init_db, get_db
from .exceptions import ServiceError
from .models import ErrorResponse, SummarizeResponse
from .routes import emails, messages, rag, summaries
from .routes.rag import ingest_emails_task

# Configure structured logging for the application
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

# Initialize the rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_REQUESTS} per {settings.RATE_LIMIT_TIMESCALE}"],
)
scheduler = AsyncIOScheduler()


async def scheduled_rag_ingestion():
    """
    Wrapper function for scheduled RAG ingestion that doesn't require user_id or request.
    This runs periodically to ingest emails for all users.
    """
    logger.info("Running scheduled RAG ingestion...")
    # For now, disable scheduled ingestion since it requires user authentication
    # In production, this would iterate through active users or use a service account
    logger.info("Scheduled RAG ingestion skipped - requires user authentication")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application lifecycle events for startup and shutdown.
    - Connects to Redis on startup.
    - Closes Redis connection on shutdown.
    - Starts and stops the RAG ingestion scheduler.
    """
    logger.info("FastAPI application startup...")
    logger.info(f"Using LLM provider: {settings.LLM_PROVIDER}")
    try:
        app.state.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        app.state.redis.ping()
        logger.info("Successfully connected to Redis.")
    except redis.exceptions.ConnectionError as e:
        logger.error("Could not connect to Redis during startup.", exc_info=e)
        app.state.redis = None
    
    # Initialize the database
    init_db()
    
    # Schedule the RAG ingestion task (disabled for local testing)
    if settings.ENVIRONMENT == "production":
        scheduler.add_job(
            scheduled_rag_ingestion,
            trigger=IntervalTrigger(hours=settings.RAG_INGESTION_INTERVAL_HOURS),
            id="rag_ingestion",
            replace_existing=True
        )
        scheduler.start()
        logger.info("RAG ingestion scheduler started", interval_hours=settings.RAG_INGESTION_INTERVAL_HOURS)
    else:
        logger.info("RAG ingestion scheduler disabled in development mode")
    
    yield
    
    if scheduler.running:
        scheduler.shutdown()
        logger.info("RAG ingestion scheduler shut down.")
        
    if app.state.redis:
        app.state.redis.close()
        logger.info("Redis connection closed.")
    logger.info("FastAPI application shutdown.")

# Initialize FastAPI app
app = FastAPI(
    title="Outlook Email Summarizer API",
    description="An API to summarize Outlook emails using LangChain and a custom GPT.",
    version="1.0.0",
    lifespan=lifespan,
)

# Include the API routers
app.include_router(emails.router)
app.include_router(messages.router)
app.include_router(rag.router)
app.include_router(summaries.router)

# Instrument the app with Prometheus metrics, exposing /metrics
Instrumentator().instrument(app).expose(app)

# Apply the rate limiter to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Be more specific in production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    """
    Global exception handler for custom ServiceError exceptions.
    Ensures that service-layer errors are converted into clean JSON responses.
    """
    logger.error("Service error occurred", message=exc.message, status_code=exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.get("/health", tags=["Monitoring"])
def health_check():
    """
    A basic health check endpoint to verify that the service is running
    and can connect to essential services like Redis.
    """
    redis_status = "ok"
    try:
        if not app.state.redis or not app.state.redis.ping():
            redis_status = "error"
    except redis.exceptions.ConnectionError:
        redis_status = "error"

    return {
        "status": "ok",
        "dependencies": {
            "redis": redis_status,
            "llm_provider": settings.LLM_PROVIDER
        }
    } 