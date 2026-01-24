"""MySQL database engine and session factory for SQLModel."""

from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session

from app.config import DATABASE_URL

# Create MySQL engine with echo=False for production (set to True for SQL query debugging)
# pool_pre_ping=True ensures connections are checked before use (handles stale connections)
# pool_recycle=3600 recycles connections after 1 hour (prevents MySQL server timeout)
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)


def get_db() -> Session:
    """Get database session.
    
    Yields:
        Session: SQLModel database session
        
    Usage:
        with get_db() as session:
            # use session
            pass
    """
    with Session(engine) as session:
        yield session


def create_tables():
    """Create all database tables.
    
    Call this once at application startup to ensure tables exist.
    """
    SQLModel.metadata.create_all(engine)

