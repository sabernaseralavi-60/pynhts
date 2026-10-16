from __future__ import annotations

import os
from pathlib import Path

CACHE = Path(__file__).resolve().parents[2] / "local_data" / "cache"
# Set at import time so that module-scoped fixtures calling ``pynhts.load(2017)`` see it.
os.environ["PYNHTS_CACHE_DIR"] = str(CACHE)
