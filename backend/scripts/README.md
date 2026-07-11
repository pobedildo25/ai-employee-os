"""Backup/restore helpers for PostgreSQL.

Backup
------
From host (with postgresql-client installed):

  set DATABASE_URL=postgresql+asyncpg://ai_employee:change-me@localhost:5433/ai_employee_os
  python backend/scripts/backup_postgres.py --output backups/local.dump

Inside backend container:

  docker compose exec backend python scripts/backup_postgres.py --output backups/container.dump

Restore
-------
  python backend/scripts/restore_postgres.py --input backups/local.dump --clean

Production tip: stop writers or take a maintenance window before --clean restore.
"""
