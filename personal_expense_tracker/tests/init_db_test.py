import asyncio
import sys
from pathlib import Path

# Project root (parent of tests/) so `import db` works when run as: python tests/init_db_test.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from db import get_engine, init_db


async def main() -> None:
    await init_db()
    engine = get_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                      AND table_name = 'expenses'
                    """
                )
            )
        ).fetchall()
        print(f"Rows: {rows}")


if __name__ == "__main__":
    asyncio.run(main())
