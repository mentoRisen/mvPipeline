"""SQLite database engine and session factory for SQLModel."""

from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session

from app.config import DB_PATH

# Create SQLite engine with check_same_thread=False for SQLModel compatibility
# and echo=False for production (set to True for SQL query debugging)
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
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

