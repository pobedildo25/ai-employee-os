#!/usr/bin/env python3
"""CLI entrypoint for agency archive ingest."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agency_archive.ingest import ingest_archive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest agency archive into knowledge/brand pipeline")
    parser.add_argument("--archive-root", required=True, help="Root directory with client documents")
    parser.add_argument("--agency-name", default="NOVA Agency")
    parser.add_argument("--max-files", type=int, default=80, help="Max files per client folder")
    parser.add_argument("--trace-id", default="agency-ingest")
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Flatten all files into one agency client (legacy)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_root = Path(args.archive_root)
    if not archive_root.exists():
        print(f"Archive path not found: {archive_root}", file=sys.stderr)
        return 1
    summary = asyncio.run(
        ingest_archive(
            archive_root=archive_root,
            agency_name=args.agency_name,
            max_files=args.max_files,
            trace_id=args.trace_id,
            per_client=not args.flat,
        )
    )
    print(summary)
    return 0 if summary.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
