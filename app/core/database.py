"""
Database connection and session management
SQLAlchemy 2.0+ with DeclarativeBase
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from typing import Generator

from app.core.config import settings


# ============================================
# DATABASE ENGINE
# ============================================

engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    echo=settings.sql_echo,
)

# ============================================
# SESSION FACTORY
# ============================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ============================================
# BASE MODEL
# ============================================

class Base(DeclarativeBase):
    pass


# ============================================
# DEPENDENCY INJECTION
# ============================================

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions
    
    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================
# DATABASE UTILITIES
# ============================================

def init_db() -> None:
    """
    Initialize database
    Creates all tables if they don't exist
    
    Note: In production, use Alembic migrations instead
    """
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """
    Drop all tables
    WARNING: This deletes all data!
    Only use in development/testing
    """
    Base.metadata.drop_all(bind=engine)