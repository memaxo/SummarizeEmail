from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import structlog

from ..config import settings
from ..rag.models import Base

logger = structlog.get_logger(__name__)

# Use the DATABASE_URL directly from settings
DATABASE_URL = settings.DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Initializes the database, creating the vector extension and any tables.
    """
    try:
        with engine.connect() as connection:
            logger.info("Initializing database...")
            # Enable the pgvector extension
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            # Create tables from SQLAlchemy models
            Base.metadata.create_all(bind=engine)
            connection.commit()
            logger.info("Database initialized successfully.")
    except OperationalError as e:
        logger.error("Could not connect to the database.", exc_info=e)
        raise

def get_db():
    """
    FastAPI dependency to provide a database session per request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 