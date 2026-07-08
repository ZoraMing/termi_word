"""数据库 Engine 与 Session 初始化"""
from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from termi_word3.database.models import Base


def create_session_factory(db_path: str | Path) -> sessionmaker:
    """创建 SQLAlchemy 会话工厂，启用外键约束和 WAL 模式。"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

    return sessionmaker(bind=engine)


def init_database(session_factory: sessionmaker) -> None:
    """初始化数据库表。"""
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    # 增量迁移：为 settings 表添加缺失的列
    with engine.begin() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info(settings)")
        existing = {row[1] for row in result}
        migrations = {
            "search_shortcut": "ALTER TABLE settings ADD COLUMN search_shortcut VARCHAR(30) DEFAULT 'ctrl+slash'",
        }
        for col, ddl in migrations.items():
            if col not in existing:
                conn.exec_driver_sql(ddl)
