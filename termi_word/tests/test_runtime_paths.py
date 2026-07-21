"""运行时数据目录解析测试。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from termi_word.runtime_paths import (
    ensure_data_directories,
    resolve_runtime_paths,
)


class TestRuntimePaths(unittest.TestCase):
    """验证开发运行和打包运行时的数据目录定位。"""

    def test_dev_paths_use_app_root_termi_data_directory(self) -> None:
        """开发态：数据目录应使用 app_root/termi_data/"""
        with TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            module_file = repo_root / "termi_word" / "runtime_paths.py"

            paths = resolve_runtime_paths(
                is_frozen=False,
                executable=Path(temp_dir) / "dist" / "termi-word.exe",
                module_file=module_file,
            )

            self.assertEqual(paths.app_root, repo_root)
            self.assertEqual(paths.data_dir, repo_root / "termi_data")
            self.assertEqual(paths.imports_dir, repo_root / "termi_data" / "imports")
            self.assertEqual(paths.db_path, repo_root / "termi_data" / "termi_word.sqlite3")

    def test_frozen_paths_use_exe_directory_termi_data(self) -> None:
        """打包态：数据目录应使用 exe 同级目录/termi_data/"""
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"

            paths = resolve_runtime_paths(
                is_frozen=True,
                executable=app_root / "termi-word.exe",
                module_file=Path(temp_dir) / "repo" / "termi_word" / "runtime_paths.py",
            )

            self.assertEqual(paths.app_root, app_root)
            self.assertEqual(paths.data_dir, app_root / "termi_data")
            self.assertEqual(paths.imports_dir, app_root / "termi_data" / "imports")
            self.assertEqual(paths.db_path, app_root / "termi_data" / "termi_word.sqlite3")

    def test_ensure_data_directories_creates_data_and_imports_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "TermiWord"

            paths = resolve_runtime_paths(
                is_frozen=True,
                executable=app_root / "termi-word",
                module_file=Path(temp_dir) / "repo" / "termi_word" / "runtime_paths.py",
            )

            ensure_data_directories(paths)

            self.assertTrue(paths.data_dir.is_dir())
            self.assertTrue(paths.imports_dir.is_dir())
            self.assertFalse(paths.db_path.exists())

    def test_runtime_paths_is_frozen_and_update_from_works(self) -> None:
        """验证 RuntimePaths 是不可变的，但 update_from 可以正确更新属性。"""
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "TermiWord"

            paths1 = resolve_runtime_paths(
                is_frozen=True,
                executable=app_root / "termi-word.exe",
                module_file=Path(temp_dir) / "repo" / "termi_word" / "runtime_paths.py",
            )

            # 创建第二个 paths 实例
            paths2 = resolve_runtime_paths(
                is_frozen=True,
                executable=app_root / "termi-word.exe",
                module_file=Path(temp_dir) / "repo" / "termi_word" / "runtime_paths.py",
            )

            # 验证 frozen 属性：不能直接赋值
            with self.assertRaises(AttributeError):
                paths1.imports_dir = Path(temp_dir) / "new_data"

            # 验证 update_from 可以更新属性
            self.assertEqual(paths1.data_dir, paths2.data_dir)
            paths1.update_from(paths2)
            self.assertEqual(paths1.data_dir, paths2.data_dir)


if __name__ == "__main__":
    unittest.main()
