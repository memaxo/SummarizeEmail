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

from . import services
from .config import settings
from .exceptions import ServiceError
from .models import ErrorResponse, SummarizeResponse

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application lifecycle events for startup and shutdown.
    - Connects to Redis on startup.
    - Closes Redis connection on shutdown.
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
    
    yield
    
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

# Instrument the app with Prometheus metrics, exposing /metrics
Instrumentator().instrument(app).expose(app)

# Apply the rate limiter to the app
app.state.limiter = limiter
app.add_exception_handler(HTTPException, _rate_limit_exceeded_handler)

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


@app.get(
    "/summarize",
    response_model=SummarizeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
        404: {"model": ErrorResponse, "description": "Email not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        502: {"model": ErrorResponse, "description": "Upstream API error"},
    },
    tags=["Summarization"],
)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS} per {settings.RATE_LIMIT_TIMESCALE}")
def summarize_email(
    request: Request,
    msg_id: str = Query(
        ...,
        description="The immutable ID of the Outlook email message.",
        examples=["AAMkAGI1ZTMx..."],
    ),
):
    """
    Summarizes a single Outlook email message.

    This endpoint orchestrates the process:
    1.  Checks for a cached summary in Redis.
    2.  If not cached, fetches the email from Microsoft Graph.
    3.  Generates a summary using the configured LLM.
    4.  Caches the new summary in Redis.
    5.  Returns the summary.
    """
    # 1. Check Redis cache first
    cached_result = None
    if app.state.redis:
        try:
            cached_result = app.state.redis.get(msg_id)
        except redis.exceptions.ConnectionError as e:
            logger.error("Could not connect to Redis for cache check", exc_info=e)
            
        if cached_result:
            logger.info("Cache hit for message_id", msg_id=msg_id)
            data = json.loads(cached_result)
            return SummarizeResponse(
                summary=data["summary"],
                message_id=msg_id,
                cached=True,
                llm_provider=data.get("llm_provider", settings.LLM_PROVIDER),
            )
            
    logger.info("Cache miss for message_id", msg_id=msg_id)

    # 2. Fetch email content from Graph API
    content = services.fetch_email_content(msg_id)

    # 3. Generate the summary
    summary = services.run_summarization_chain(content)

    response_data = {
        "summary": summary,
        "message_id": msg_id,
        "cached": False,
        "llm_provider": settings.LLM_PROVIDER,
    }

    # 4. Cache the new summary in Redis
    if app.state.redis:
        try:
            logger.info("Setting cache for message_id", msg_id=msg_id)
            app.state.redis.set(msg_id, json.dumps(response_data), ex=settings.REDIS_CACHE_TTL)
        except redis.exceptions.ConnectionError as e:
            logger.error("Could not connect to Redis to set cache", exc_info=e)

    # 5. Return the response
    return SummarizeResponse(**response_data) 