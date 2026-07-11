#!/usr/bin/env python3
"""Create a PostgreSQL logical backup (pg_dump).

Usage:
  export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
  python backend/scripts/backup_postgres.py [--output backups/backup.dump]

Requires: pg_dump (postgresql-client) on PATH.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote


def to_libpq_url(database_url: str) -> str:
    url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup PostgreSQL database")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="SQLAlchemy/asyncpg URL or libpq URL",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output dump path (default: backups/ai_employee_os_YYYYMMDD_HHMMSS.dump)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 1

    libpq_url = to_libpq_url(args.database_url)
    parsed = urlparse(libpq_url)
    db_name = (parsed.path or "/ai_employee_os").lstrip("/") or "ai_employee_os"

    output = args.output
    if not output:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = str(Path("backups") / f"{db_name}_{stamp}.dump")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)

    cmd = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        f"--dbname={libpq_url}",
        f"--file={output_path}",
    ]
    print(f"Creating backup: {output_path}")
    result = subprocess.run(cmd, env=env, check=False)
    if result.returncode != 0:
        print("pg_dump failed", file=sys.stderr)
        return result.returncode
    print(f"Backup complete: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
