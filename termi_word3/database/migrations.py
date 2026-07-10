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
}


def apply_lightweight_migrations(engine: Engine) -> None:
    """执行 SQLite 数据库轻量表结构补丁升级"""
    with engine.begin() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info(settings)")
        existing = {row[1] for row in result}
        for column, ddl in SETTINGS_COLUMNS.items():
            if column not in existing:
                conn.exec_driver_sql(ddl)
