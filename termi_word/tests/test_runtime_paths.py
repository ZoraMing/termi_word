"""运行时数据目录解析测试。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from termi_word.runtime_paths import (
    ensure_data_directories,
    resolve_runtime_paths,
    save_runtime_path_overrides,
)


class TestRuntimePaths(unittest.TestCase):
    """验证开发运行和打包运行时的数据目录定位。"""

    def test_dev_paths_use_project_data_directory(self) -> None:
        module_file = Path("E:/repo/termi_word/runtime_paths.py")

        paths = resolve_runtime_paths(
            is_frozen=False,
            executable=Path("E:/dist/TermiWord/termi-word.exe"),
            module_file=module_file,
        )

        self.assertEqual(paths.app_root, Path("E:/repo"))
        self.assertEqual(paths.data_dir, Path("E:/repo/data"))
        self.assertEqual(paths.imports_dir, Path("E:/repo/data/imports"))
        self.assertEqual(paths.db_path, Path("E:/repo/data/termi_word.sqlite3"))
        self.assertEqual(paths.ui_config_path, Path("E:/repo/data/ui_config.json"))

    def test_frozen_paths_use_executable_side_data_directory(self) -> None:
        executable = Path("D:/apps/TermiWord/termi-word.exe")

        paths = resolve_runtime_paths(
            is_frozen=True,
            executable=executable,
            module_file=Path("E:/repo/termi_word/runtime_paths.py"),
        )

        self.assertEqual(paths.app_root, Path("D:/apps/TermiWord"))
        self.assertEqual(paths.data_dir, Path("D:/apps/TermiWord/data"))
        self.assertEqual(paths.imports_dir, Path("D:/apps/TermiWord/data/imports"))
        self.assertEqual(paths.db_path, Path("D:/apps/TermiWord/data/termi_word.sqlite3"))
        self.assertEqual(paths.ui_config_path, Path("D:/apps/TermiWord/data/ui_config.json"))

    def test_paths_json_overrides_imports_and_config_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "TermiWord"
            bootstrap_dir = app_root / "data"
            bootstrap_dir.mkdir(parents=True)
            config_dir = Path(temp_dir) / "external" / "data"
            (bootstrap_dir / "paths.json").write_text(
                (
                    "{\n"
                    f"  \"config_dir\": \"{config_dir.as_posix()}\"\n"
                    "}\n"
                ),
                encoding="utf-8",
            )

            paths = resolve_runtime_paths(
                is_frozen=True,
                executable=app_root / "termi-word.exe",
                module_file=Path("E:/repo/termi_word/runtime_paths.py"),
            )

            self.assertEqual(paths.data_dir, config_dir)
            self.assertEqual(paths.imports_dir, config_dir / "imports")
            self.assertEqual(paths.db_path, config_dir / "termi_word.sqlite3")
            self.assertEqual(paths.ui_config_path, config_dir / "ui_config.json")
            self.assertEqual(paths.paths_config_path, bootstrap_dir / "paths.json")

    def test_save_runtime_path_overrides_writes_bootstrap_config_and_creates_dirs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "TermiWord"
            data_dir = Path(temp_dir) / "external" / "data"

            saved_path = save_runtime_path_overrides(
                app_root=app_root,
                data_dir=data_dir,
            )

            self.assertEqual(saved_path, app_root / "data" / "paths.json")
            self.assertTrue(data_dir.is_dir())
            self.assertTrue((data_dir / "imports").is_dir())
            text = saved_path.read_text(encoding="utf-8")
            self.assertIn(data_dir.as_posix(), text)

    def test_save_runtime_path_overrides_resolves_relative_paths_from_app_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "TermiWord"

            saved_path = save_runtime_path_overrides(
                app_root=app_root,
                data_dir="custom/data",
            )

            text = saved_path.read_text(encoding="utf-8")
            # 应该保存为相对路径以提升便携性
            self.assertIn('"config_dir": "custom/data"', text)

    def test_save_runtime_path_overrides_cleans_quotes_and_spaces(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "TermiWord"

            saved_path = save_runtime_path_overrides(
                app_root=app_root,
                data_dir=' "custom\\data" ',
            )

            import json
            data = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertEqual(data["config_dir"], "custom/data")

    def test_ensure_data_directories_creates_data_and_imports_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            paths = resolve_runtime_paths(
                is_frozen=True,
                executable=Path(temp_dir) / "TermiWord" / "termi-word",
                module_file=Path("E:/repo/termi_word/runtime_paths.py"),
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
                module_file=Path("E:/repo/termi_word/runtime_paths.py"),
            )

            # 创建第二个 paths 实例，使用不同的路径
            new_data = Path(temp_dir) / "new_data"
            (app_root / "data").mkdir(parents=True, exist_ok=True)
            (app_root / "data" / "paths.json").write_text(
                json.dumps({
                    "config_dir": new_data.as_posix(),
                }),
                encoding="utf-8",
            )
            paths2 = resolve_runtime_paths(
                is_frozen=True,
                executable=app_root / "termi-word.exe",
                module_file=Path("E:/repo/termi_word/runtime_paths.py"),
            )

            # 验证 frozen 属性：不能直接赋值
            with self.assertRaises(AttributeError):
                paths1.imports_dir = new_data

            # 验证 update_from 可以更新属性
            self.assertNotEqual(paths1.data_dir, paths2.data_dir)
            paths1.update_from(paths2)
            self.assertEqual(paths1.data_dir, new_data)
            self.assertEqual(paths1.imports_dir, new_data / "imports")


if __name__ == "__main__":
    unittest.main()
