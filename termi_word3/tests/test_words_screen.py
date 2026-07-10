"""词表页交互行为回归测试。"""
from __future__ import annotations

import unittest

from termi_word3.screens.words import WordsScreen


class FakeInput:
    """记录输入框聚焦和数值变化。"""

    def __init__(self, value: str) -> None:
        self.value = value
        self.focused = False

    def focus(self) -> None:
        self.focused = True


class TestWordsScreenSearch(unittest.TestCase):
    """验证全局搜索复用词表页时不破坏当前输入状态。"""

    def test_focus_search_input_preserves_existing_query_by_default(self) -> None:
        screen = WordsScreen.__new__(WordsScreen)
        input_widget = FakeInput("abc")
        rendered: list[bool] = []

        screen.search_query = "abc"
        screen.query_one = lambda *args, **kwargs: input_widget
        screen.call_later = lambda callback: rendered.append(True)
        screen.render_words = lambda: None

        screen.focus_search_input()

        self.assertEqual(input_widget.value, "abc")
        self.assertEqual(screen.search_query, "abc")
        self.assertTrue(input_widget.focused)
        self.assertEqual(rendered, [True])


if __name__ == "__main__":
    unittest.main()
