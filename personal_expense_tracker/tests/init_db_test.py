import sys
from pathlib import Path

# Project root (parent of tests/) so `import db` works when run as: python tests/init_db_test.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_connection, init_db

init_db()
conn = get_connection()
rows = conn.execute(
    "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()
conn.close()
print(rows)
