"""CSV 格式单词数据导入服务"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from sqlalchemy.orm import sessionmaker

from termi_word.database.repositories import AppRepository
from termi_word.domain.results import ImportResult

CSV_FIELDS = ("w", "c", "zh", "en", "us", "core", "ex", "exz")


@dataclass(frozen=True)
class ImportRow:
    """导入行的数据封装"""
    row_number: int
    values: dict[str, str]


class ImportService:
    """负责将 CSV 格式的词表数据导入到本地 SQLite 数据库中。"""

    BATCH_SIZE = 200

    def __init__(self, session_factory: sessionmaker, csv_path: Path | None = None) -> None:
        self.session_factory = session_factory
        self._csv_path = csv_path

    @property
    def csv_path(self) -> Path:
        if self._csv_path is not None:
            return self._csv_path
        from termi_word.config import DEFAULT_CSV_PATH
        return DEFAULT_CSV_PATH

    def available_decks(self) -> list[str]:
        """获取导入目录下所有可用的词书（CSV 文件名，不含扩展名）。"""
        data_dir = Path(self.csv_path).parent
        if not data_dir.exists():
            return []
        decks = []
        for csv_file in sorted(data_dir.glob("*.csv")):
            deck_name = csv_file.stem
            if deck_name and not deck_name.startswith("."):
                decks.append(deck_name)
        return decks

    def source_path(self, deck_name: str) -> Path:
        """获取指定词本的 CSV 文件路径"""
        csv_path = Path(self.csv_path) if isinstance(self.csv_path, str) else self.csv_path
        data_dir = csv_path.parent
        deck_csv = data_dir / f"{deck_name}.csv"
        return deck_csv if deck_csv.exists() else csv_path

    def read_source_rows(self, deck_name: str) -> tuple[Path, list[ImportRow], tuple[str, ...]]:
        """读取 CSV 源文件的行数据，自动适配用户自定义字段映射。"""
        csv_to_use = self.source_path(deck_name)
        if not csv_to_use.exists():
            return csv_to_use, [], ()

        # 从数据库加载映射关系
        column_mapping = {}
        try:
            with self.session_factory() as session:
                s = AppRepository(session).get_settings()
                if s.csv_column_mapping:
                    column_mapping = json.loads(s.csv_column_mapping)
        except Exception:
            pass

        # 默认没有映射的退回到原样字段名
        for field in CSV_FIELDS:
            if field not in column_mapping or not column_mapping[field]:
                column_mapping[field] = field

        with csv_to_use.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            # 校验 CSV 是否包含我们绑定映射指向的那个 CSV 列名
            missing = tuple(
                field for field in CSV_FIELDS 
                if column_mapping[field] not in (reader.fieldnames or [])
            )
            if missing:
                return csv_to_use, [], missing
            rows = [
                ImportRow(
                    row_number=index,
                    values={field: (row.get(column_mapping[field]) or "").strip() for field in CSV_FIELDS},
                )
                for index, row in enumerate(reader, start=1)
            ]
        return csv_to_use, rows, ()

    def ensure_initial_data(self) -> None:
        """检查数据库，扫描导入目录下所有 CSV，并将未导入的词书自动导入。"""
        decks = self.available_decks()
        data_dir = Path(self.csv_path).parent
        for deck_name in decks:
            with self.session_factory() as session:
                repo = AppRepository(session)
                deck = repo.get_or_create_deck(deck_name)
                should_import = repo.word_count(deck.id) == 0
                session.commit()
            # 如果这个词本的单词数是 0，说明从未导入，则执行同步
            if should_import:
                csv_file = data_dir / f"{deck_name}.csv"
                if csv_file.exists():
                    try:
                        self.import_from_csv(csv_file, deck_name)
                    except Exception:
                        pass

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
                with path.open("r", encoding="utf-8-sig") as file:
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

    def import_rows(self, deck_name: str, skip_rows: set[int] | None = None) -> ImportResult:
        """导入行数据到数据库"""
        csv_to_use, rows, missing = self.read_source_rows(deck_name)
        if not csv_to_use.exists():
            return ImportResult(source_missing=str(csv_to_use))
        if missing:
            return ImportResult(missing_fields=missing)

        skip_rows = skip_rows or set()
        return self.import_prepared_rows(deck_name, rows, skip_rows)

    def import_prepared_rows(
        self,
        deck_name: str,
        rows: list[ImportRow],
        skip_rows: set[int] | None = None,
    ) -> ImportResult:
        """导入已读取的行数据，供 UI worker 按批取消。"""
        skip_rows = skip_rows or set()
        imported = 0
        updated = 0
        skipped = 0

        with self.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.get_or_create_deck(deck_name)

            for row in rows:
                if row.row_number in skip_rows:
                    skipped += 1
                    continue
                status = repo.upsert_word(deck, row.values)
                if status == "inserted":
                    imported += 1
                elif status == "updated":
                    updated += 1
                else:
                    skipped += 1

            session.commit()

        return ImportResult(imported=imported, updated=updated, skipped=skipped)
