"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CHECKPOINT_DB = DATA_DIR / "checkpoints.db"

CHAT_MODEL = os.environ.get("MAARS_CHAT_MODEL", "gemini-3-flash-preview")
REFINE_MAX_ROUND = int(os.environ.get("MAARS_REFINE_MAX_ROUND", "5"))
