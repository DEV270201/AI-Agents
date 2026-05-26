"""MySQL access for the expense tracker via async SQLAlchemy + connection pooling."""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from dotenv import load_dotenv

_ENGINE: Optional[AsyncEngine] = None


def get_engine() -> AsyncEngine:
    """Return a process-global async SQLAlchemy engine (with pooling)."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    url = os.getenv("MYSQL_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "MYSQL_DATABASE_URL is not set. "
            "Example: mysql+aiomysql://user:pass@host:3306/dbname"
        )

    _ENGINE = create_async_engine(
        url,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
        pool_pre_ping=True,
    )
    return _ENGINE


async def init_db() -> None:
    # Load variables from .env into the system environment
    load_dotenv()
    """Ensure the expenses table and index exist (non-destructive)."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS expenses (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      occurred_at DATE NOT NULL,
      amount INT NOT NULL,
      currency CHAR(3) NOT NULL DEFAULT 'USD',
      category VARCHAR(32) NOT NULL,
      notes VARCHAR(255),
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_expenses_occurred_at (occurred_at)
    )
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(create_sql))
