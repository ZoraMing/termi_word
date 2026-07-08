"""CSV 格式单词数据导入服务"""
from __future__ import annotations

import csv
from pathlib import Path
from sqlalchemy.orm import sessionmaker

from termi_word3.config import DEFAULT_CSV_PATH
from termi_word3.database.repositories import AppRepository


class ImportService:
    """负责将 CSV 格式的词表数据导入到本地 SQLite 数据库中。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def ensure_initial_data(self) -> None:
        """检查数据库，若为空则导入默认的 CSV 数据。"""
        path = Path(DEFAULT_CSV_PATH)
        if not path.exists():
            return
        with self.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            # 如果目前没有活跃的词本，或者词本中没有任何单词，则自动执行导入
            if deck is None or repo.word_count(deck.id) == 0:
                self.import_from_csv(path, "CET6")

    def import_from_csv(self, path: Path | str, deck_name: str) -> int:
        """从 CSV 读入，并持久化到指定的词本中。返回成功导入的单词数量。"""
        path = Path(path)
        if not path.exists():
            return 0
        imported = 0
        with self.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.get_or_create_deck(deck_name)
            try:
                with path.open("r", encoding="utf-8") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        word = repo.add_word_if_missing(deck, row)
                        if word is not None:
                            imported += 1
                session.commit()
            except Exception as e:
                session.rollback()
                raise e
        return imported
