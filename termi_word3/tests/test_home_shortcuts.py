"""首页快捷键配置测试。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from termi_word3.services.home_shortcut_service import (
    DEFAULT_HOME_SHORTCUTS,
    format_home_help,
    format_home_menu,
    home_shortcuts_from_setting,
    validate_home_shortcuts,
)


class TestHomeShortcuts(unittest.TestCase):
    """验证首页快捷键默认值、展示和冲突校验。"""

    def test_default_home_shortcuts_are_contiguous(self) -> None:
        setting = SimpleNamespace()

        shortcuts = home_shortcuts_from_setting(setting)

        self.assertEqual(shortcuts, DEFAULT_HOME_SHORTCUTS)
        self.assertEqual(format_home_menu(shortcuts), "[1]学习  [2]复习  [3]拼写  [4]词表  [5]日历  [6]设置")
        self.assertIn("3-拼写", format_home_help(shortcuts))

    def test_home_shortcuts_reject_duplicates(self) -> None:
        shortcuts = dict(DEFAULT_HOME_SHORTCUTS)
        shortcuts["settings"] = shortcuts["study"]

        with self.assertRaisesRegex(ValueError, "同时绑定"):
            validate_home_shortcuts(shortcuts)

    def test_home_shortcuts_reject_reserved_global_shortcut(self) -> None:
        shortcuts = dict(DEFAULT_HOME_SHORTCUTS)
        shortcuts["study"] = "ctrl+slash"

        with self.assertRaisesRegex(ValueError, "已被全局功能占用"):
            validate_home_shortcuts(shortcuts, reserved={"ctrl+slash"})


if __name__ == "__main__":
    unittest.main()
