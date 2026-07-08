from __future__ import annotations

from pathlib import Path

APP_TITLE = "Termi Word"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "termi_word.sqlite3"
WORDS_CSV = DATA_DIR / "words.csv"
UI_CONFIG_PATH = DATA_DIR / "ui_config.json"

DEFAULT_DECK_NAME = "default"
DEFAULT_DAILY_NEW_TARGET = 20
DEFAULT_REVIEW_SOFT_LIMIT = 100

PANEL_WIDTH = 72
MIN_PANEL_HEIGHT = 6
MAX_PANEL_HEIGHT = 12
