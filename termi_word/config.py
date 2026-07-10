"""Termi Word 3 配置"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "words.db"
DEFAULT_CSV_PATH = DATA_DIR / "words.csv"

APP_TITLE = "Termi Word"
APP_VERSION = "1.0.0"

# 学习默认参数
DEFAULT_DAILY_NEW_TARGET = 20
DEFAULT_REVIEW_SOFT_LIMIT = 100
DEFAULT_DAILY_SPELLING_TARGET = 15
