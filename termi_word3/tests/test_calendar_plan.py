"""日历页每日计划选择回归测试。"""
from __future__ import annotations

import unittest

from termi_word3.screens.calendar import CalendarScreen


class TestCalendarPlanFields(unittest.TestCase):
    """验证日历页浏览态也展示可选择的学习计划字段。"""

    def test_plan_field_lines_include_selected_cursor_in_browse_mode(self) -> None:
        screen = CalendarScreen.__new__(CalendarScreen)
        screen.selected = 1
        screen.values = {
            "daily_new_target": 10,
            "review_soft_limit": 20,
            "daily_spelling_target": 5,
        }

        lines = screen._plan_field_lines(editing=False)

        self.assertEqual(len(lines), 3)
        self.assertIn("每轮复习", lines[1])
        self.assertIn("20", lines[1])
        self.assertNotEqual(lines[0], lines[1])


if __name__ == "__main__":
    unittest.main()
