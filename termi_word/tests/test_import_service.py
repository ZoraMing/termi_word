"""CSV 导入服务回归测试。"""
from __future__ import annotations

import sqlite3
import unittest
import gc
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from termi_word.database.engine import create_session_factory, init_database
from termi_word.screens.deck_config import DeckConfigScreen
from termi_word.services.import_service import ImportService


class TestImportService(unittest.TestCase):
    """验证 CSV 导入对真实文件编码和目录结构的兼容。"""

    def test_import_from_csv_accepts_utf8_bom_header(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "imports" / "demo.csv"
            csv_path.parent.mkdir()
            csv_path.write_text(
                "w,c,zh,en,us,core,ex,exz\nhello,n,greeting,,,,,\n",
                encoding="utf-8-sig",
            )
            db_path = root / "data" / "termi_word.sqlite3"
            session_factory = create_session_factory(db_path)
            init_database(session_factory)

            try:
                imported = ImportService(session_factory, csv_path).import_from_csv(csv_path, "demo")

                self.assertEqual(imported, 1)
                connection = sqlite3.connect(db_path)
                try:
                    word_count = connection.execute("SELECT COUNT(*) FROM words").fetchone()[0]
                finally:
                    connection.close()
                self.assertEqual(word_count, 1)
            finally:
                session_factory.kw["bind"].dispose()
                gc.collect()

    def test_ensure_initial_data_imports_csv_from_imports_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "data" / "imports" / "demo.csv"
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "w,c,zh,en,us,core,ex,exz\nhello,n,greeting,,,,,\n",
                encoding="utf-8-sig",
            )
            db_path = root / "data" / "termi_word.sqlite3"
            session_factory = create_session_factory(db_path)
            init_database(session_factory)

            try:
                ImportService(session_factory, csv_path).ensure_initial_data()

                connection = sqlite3.connect(db_path)
                try:
                    deck_count = connection.execute("SELECT COUNT(*) FROM decks").fetchone()[0]
                    word_count = connection.execute("SELECT COUNT(*) FROM words").fetchone()[0]
                    card_count = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
                finally:
                    connection.close()
                self.assertEqual(deck_count, 1)
                self.assertEqual(word_count, 1)
                self.assertEqual(card_count, 1)
            finally:
                session_factory.kw["bind"].dispose()
                gc.collect()


class TestDeckConfigCsvDiscovery(unittest.TestCase):
    """验证词书设置页扫描外部导入目录。"""

    def test_scan_csv_files_uses_imports_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            imports_dir = data_dir / "imports"
            imports_dir.mkdir(parents=True)
            (imports_dir / "demo.csv").write_text("w,zh\nhello,greeting\n", encoding="utf-8")

            with patch("termi_word.screens.deck_config.IMPORTS_DIR", imports_dir):
                screen = DeckConfigScreen()
                screen.scan_csv_files()

            self.assertEqual(screen.csv_files, ["demo.csv"])


if __name__ == "__main__":
    unittest.main()
