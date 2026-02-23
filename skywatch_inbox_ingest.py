#!/usr/bin/env python3
"""Ingest SkyWatch uploads from vsftpd inbox and update dashboard images."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

SKYCAM_DIR = Path("/srv/doro_lab_projects/skycam")
INBOX_DIR = SKYCAM_DIR / "inbox"
LATEST_PATH = SKYCAM_DIR / "sky_latest_web.jpg"
IMAGES_DIR = SKYCAM_DIR / "images"  # Put in root images, not subdirectory
ARCHIVE_DIR = SKYCAM_DIR / "archive"
STATUS_FILE = SKYCAM_DIR / "skywatch_status.json"


def _newest_jpg(path: Path):
    files = list(path.glob("*.jpg")) + list(path.glob("*.jpeg"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def ingest_latest():
    newest = _newest_jpg(INBOX_DIR)
    if not newest:
        return False

    # Copy to latest
    shutil.copy2(newest, LATEST_PATH)

    # Copy to gallery
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(newest, IMAGES_DIR / newest.name)

    # Archive by date
    archive_subdir = ARCHIVE_DIR / datetime.now(timezone.utc).strftime("%Y/%m/%d")
    archive_subdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(newest, archive_subdir / newest.name)

    # Update status
    status = {
        "last_event": "image_received",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_filename": newest.name,
        "last_size_bytes": newest.stat().st_size,
        "connection": "active",
    }
    STATUS_FILE.write_text(json.dumps(status, indent=2))

    return True


if __name__ == "__main__":
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ingest_latest()
