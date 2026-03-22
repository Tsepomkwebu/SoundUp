"""
Tool: cleanup_tmp.py
Deletes processed output files older than FILE_TTL_SECONDS (default 1 hour).
Run manually or via cron: */30 * * * * python /path/to/tools/cleanup_tmp.py
"""

import os
import time
from pathlib import Path

TTL_SECONDS = int(os.getenv("FILE_TTL_SECONDS", 3600))

DIRS_TO_CLEAN = [
    Path(".tmp/uploads"),
    Path(".tmp/audio"),
    Path(".tmp/output"),
]


def cleanup():
    now = time.time()
    removed = 0

    for directory in DIRS_TO_CLEAN:
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.is_file() and (now - f.stat().st_mtime) > TTL_SECONDS:
                f.unlink()
                removed += 1
                print(f"Removed: {f}")

    print(f"Cleanup complete. {removed} file(s) removed.")


if __name__ == "__main__":
    cleanup()
