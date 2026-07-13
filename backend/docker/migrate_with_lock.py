"""Run alembic upgrade head under a Postgres advisory lock.

Prevents concurrent containers from racing migrations when
RUN_MIGRATIONS_ON_STARTUP=true on scaled API replicas.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

# Arbitrary stable key for AI Employee OS migrations.
_MIGRATION_LOCK_KEY = 872_514_001


def _asyncpg_dsn(database_url: str) -> str:
    url = database_url.strip()
    for prefix in ("postgresql+asyncpg://", "postgres+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix) :]
    return url


async def _run_with_lock() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is required for migrations", file=sys.stderr)
        return 1

    import asyncpg

    dsn = _asyncpg_dsn(database_url)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", _MIGRATION_LOCK_KEY)
        print(f"Acquired migration advisory lock ({_MIGRATION_LOCK_KEY})")
        proc = subprocess.run(["alembic", "upgrade", "head"], check=False)
        return int(proc.returncode)
    finally:
        try:
            await conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_LOCK_KEY)
        except Exception as exc:  # noqa: BLE001 — best-effort unlock
            print(f"Warning: failed to unlock migration advisory lock: {exc}", file=sys.stderr)
        await conn.close()


def main() -> int:
    return asyncio.run(_run_with_lock())


if __name__ == "__main__":
    raise SystemExit(main())
