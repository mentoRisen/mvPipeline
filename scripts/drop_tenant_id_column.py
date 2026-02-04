"""One-off script to drop the tenant_id column from tenants table.

Run this if you have an existing database created before tenant_id was removed.
Usage: python scripts/drop_tenant_id_column.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from app.db.engine import engine
from app.config import DATABASE_URL


def main():
    with engine.connect() as conn:
        if "mysql" in DATABASE_URL:
            r = conn.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tenants' AND COLUMN_NAME = 'tenant_id'
            """))
            if r.fetchone() is None:
                print("Column tenant_id does not exist. Nothing to do.")
                return
        try:
            conn.execute(text("ALTER TABLE tenants DROP COLUMN tenant_id"))
            conn.commit()
            print("Dropped tenant_id column from tenants table.")
        except Exception as e:
            conn.rollback()
            raise SystemExit(f"Error: {e}") from e


if __name__ == "__main__":
    main()
