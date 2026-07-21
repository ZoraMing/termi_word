"""数据库 Engine 与 Session 初始化"""
from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from termi_word.database.models import Base
from termi_word.database.migrations import apply_lightweight_migrations

# 全局会话工厂引用，供服务层使用
_session_factory: sessionmaker | None = None


def create_session_factory(db_path: str | Path) -> sessionmaker:
    """创建 SQLAlchemy 会话工厂，启用外键约束和 WAL 模式。"""
    global _session_factory
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False, connect_args={"timeout": 15.0})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

    _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory


def get_session_factory() -> sessionmaker:
    """获取全局会话工厂。"""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call create_session_factory first.")
    return _session_factory


def init_database(session_factory: sessionmaker) -> None:
    """初始化数据库表并执行轻量迁移。"""
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)
    apply_lightweight_migrations(engine)
