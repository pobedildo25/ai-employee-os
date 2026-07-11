#!/usr/bin/env python3
"""Restore a PostgreSQL logical backup created by backup_postgres.py.

Usage:
  export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
  python backend/scripts/restore_postgres.py --input backups/backup.dump

Requires: pg_restore (postgresql-client) on PATH.
Warning: restores into the target database; use a maintenance window.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote


def to_libpq_url(database_url: str) -> str:
    url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore PostgreSQL database")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="SQLAlchemy/asyncpg URL or libpq URL",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to custom-format dump from backup_postgres.py",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Drop database objects before recreate (pg_restore --clean)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 1

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Backup file not found: {input_path}", file=sys.stderr)
        return 1

    libpq_url = to_libpq_url(args.database_url)
    parsed = urlparse(libpq_url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)

    cmd = [
        "pg_restore",
        "--no-owner",
        "--no-acl",
        "--dbname",
        libpq_url,
        str(input_path),
    ]
    if args.clean:
        cmd.insert(1, "--clean")
        cmd.insert(2, "--if-exists")

    print(f"Restoring backup: {input_path}")
    result = subprocess.run(cmd, env=env, check=False)
    # pg_restore may return 1 for non-fatal warnings; treat >=2 as hard failure.
    if result.returncode >= 2:
        print("pg_restore failed", file=sys.stderr)
        return result.returncode
    print("Restore complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
