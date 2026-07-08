from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from termi_word.database.models import Base


def create_session_factory(db_path: Path) -> sessionmaker[Session]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_database(session_factory: sessionmaker[Session]) -> None:
    Base.metadata.create_all(session_factory.kw["bind"])
