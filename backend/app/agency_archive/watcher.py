"""Poll agency archive directory and re-ingest when content changes."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)


class AgencyArchiveWatcher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_fingerprint: str | None = None

    async def start(self) -> None:
        if not self._settings.agency_archive_watch_enabled:
            logger.info("Agency archive watcher disabled")
            return
        root = Path(self._settings.agency_archive_path)
        if not root.exists():
            logger.warning("Agency archive path missing, watcher idle: %s", root)
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="agency-archive-watcher")
        logger.info("Agency archive watcher started | path=%s", root)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        interval = max(5, int(self._settings.agency_archive_watch_interval_seconds))
        # Initial sync
        await self._sync_if_changed(force=True)
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                await self._sync_if_changed(force=False)

    async def _sync_if_changed(self, *, force: bool) -> None:
        root = Path(self._settings.agency_archive_path)
        if not root.exists():
            return
        fingerprint = _fingerprint_tree(root)
        if not force and fingerprint == self._last_fingerprint:
            return
        try:
            from app.agency_archive.ingest import ingest_archive

            summary = await ingest_archive(
                archive_root=root,
                agency_name=self._settings.agency_archive_agency_name,
                max_files=self._settings.agency_archive_max_files_per_client,
                trace_id="agency-archive-watch",
                per_client=True,
            )
            self._last_fingerprint = fingerprint
            logger.info("Agency archive sync complete | summary=%s", summary)
        except Exception:
            logger.exception("Agency archive sync failed")


def _fingerprint_tree(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda p: str(p),
    )
    for path in files[:5000]:
        try:
            stat = path.stat()
        except OSError:
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8", errors="ignore"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(str(stat.st_size).encode("ascii"))
    return digest.hexdigest()
