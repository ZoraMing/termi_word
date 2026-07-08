from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from termi_word.config import WORDS_CSV
from termi_word.database.repositories import AppRepository
from termi_word.services.config_service import ConfigService

CSV_FIELDS = ("w", "c", "zh", "en", "us", "core", "ex", "exz")


class ImportService:
    def __init__(self, session_factory: sessionmaker[Session], csv_path: Path = WORDS_CSV) -> None:
        self.session_factory = session_factory
        self.csv_path = csv_path

    def ensure_initial_data(self, deck_name: str) -> str:
        # 优先使用与词包名匹配的专有 CSV，如果不存在则回退至默认的 words.csv
        deck_csv = self.csv_path.parent / f"{deck_name}.csv"
        csv_to_use = deck_csv if deck_csv.exists() else self.csv_path

        if not csv_to_use.exists():
            return f"找不到词表：{csv_to_use}"

        with self.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.get_or_create_deck(deck_name)
            
            # 读取当前配置中的导入行号限制
            config = ConfigService().load()
            start_row = config.import_start_row
            end_row = config.import_end_row

            imported = 0
            skipped = 0

            with csv_to_use.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                missing = [field for field in CSV_FIELDS if field not in (reader.fieldnames or [])]
                if missing:
                    return f"词表字段缺失：{', '.join(missing)}"
                
                for idx, row in enumerate(reader, start=1):
                    # 进行行号范围适配
                    if start_row > 0 and idx < start_row:
                        continue
                    if end_row > 0 and idx > end_row:
                        break

                    if repo.add_word(deck, row):
                        imported += 1
                    else:
                        skipped += 1

            session.commit()
            
            # 若没有任何新词导入，但跳过了已存在的单词，说明词表该部分已就绪
            if imported == 0 and skipped > 0:
                return "词表已就绪"
            return f"已导入 {imported} 个单词"

