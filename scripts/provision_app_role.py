"""Create or update the non-owner API role that row-level security applies to.

Run as the database owner after migrating:
    $env:APP_DB_PASSWORD = '<random secret>'
    uv run python scripts/provision_app_role.py --role regintel_app

Then point the API's DATABASE_URL at that role. Migrations and ingestion keep
using the owner URL. The role gets DML on application tables only, no DDL.
"""

import argparse
import os

from sqlalchemy import create_engine

from regintel.core.config import get_settings
from regintel.db.roles import provision


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--role", default="regintel_app")
    args = parser.parse_args()
    password = os.environ.get("APP_DB_PASSWORD", "")
    if len(password) < 16:
        raise SystemExit("Set APP_DB_PASSWORD to a random secret of at least 16 characters")
    provision(create_engine(get_settings().database_url), args.role, password)
    print(f"Role {args.role} provisioned without superuser or BYPASSRLS")


if __name__ == "__main__":
    main()
