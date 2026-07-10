"""SQLite 轻量迁移。"""
from __future__ import annotations

from sqlalchemy.engine import Engine


# 全局系统设置表新增列补丁迁移定义
SETTINGS_COLUMNS = {
    "search_shortcut": "ALTER TABLE settings ADD COLUMN search_shortcut VARCHAR(30) DEFAULT 'ctrl+slash'",
    "panel_max_width": "ALTER TABLE settings ADD COLUMN panel_max_width INTEGER DEFAULT 120",
    "panel_min_height": "ALTER TABLE settings ADD COLUMN panel_min_height INTEGER DEFAULT 6",
    "panel_max_height": "ALTER TABLE settings ADD COLUMN panel_max_height INTEGER DEFAULT 16",
    "csv_column_mapping": "ALTER TABLE settings ADD COLUMN csv_column_mapping TEXT",
    "timezone_offset_minutes": "ALTER TABLE settings ADD COLUMN timezone_offset_minutes INTEGER",
    "home_key_study": "ALTER TABLE settings ADD COLUMN home_key_study VARCHAR(30) DEFAULT '1'",
    "home_key_review": "ALTER TABLE settings ADD COLUMN home_key_review VARCHAR(30) DEFAULT '2'",
    "home_key_spelling": "ALTER TABLE settings ADD COLUMN home_key_spelling VARCHAR(30) DEFAULT '3'",
    "home_key_words": "ALTER TABLE settings ADD COLUMN home_key_words VARCHAR(30) DEFAULT '4'",
    "home_key_calendar": "ALTER TABLE settings ADD COLUMN home_key_calendar VARCHAR(30) DEFAULT '5'",
    "home_key_settings": "ALTER TABLE settings ADD COLUMN home_key_settings VARCHAR(30) DEFAULT '6'",
}


STUDY_SESSION_COLUMNS = {
    "session_date": "ALTER TABLE study_sessions ADD COLUMN session_date DATE",
}


def apply_lightweight_migrations(engine: Engine) -> None:
    """执行 SQLite 数据库轻量表结构补丁升级"""
    with engine.begin() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info(settings)")
        existing = {row[1] for row in result}
        for column, ddl in SETTINGS_COLUMNS.items():
            if column not in existing:
                conn.exec_driver_sql(ddl)

        result = conn.exec_driver_sql("PRAGMA table_info(study_sessions)")
        existing = {row[1] for row in result}
        for column, ddl in STUDY_SESSION_COLUMNS.items():
            if column not in existing:
                conn.exec_driver_sql(ddl)
