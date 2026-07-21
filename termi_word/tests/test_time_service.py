"""本地时区配置服务测试。"""
from __future__ import annotations

import datetime
import unittest

from termi_word.services.time_service import (
    TimeSettingsService,
    format_offset,
    parse_offset,
    system_timezone_offset_minutes,
)


class TestTimeSettingsService(unittest.TestCase):
    """验证时区解析和格式化。"""

    def test_parse_and_format_timezone_offset(self) -> None:
        self.assertEqual(parse_offset("+08:00"), 480)
        self.assertEqual(parse_offset("-05:30"), -330)
        self.assertEqual(format_offset(480), "+08:00")
        self.assertEqual(format_offset(-330), "-05:30")

    def test_parse_invalid_format_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            parse_offset("invalid")
        with self.assertRaises(ValueError):
            parse_offset("+15:00")  # 超出范围
        with self.assertRaises(ValueError):
            parse_offset("+08:60")  # 分钟超出范围

    def test_system_timezone_offset_returns_integer(self) -> None:
        offset = system_timezone_offset_minutes()
        self.assertIsInstance(offset, int)
        # 合理范围：-12 到 +14 小时
        self.assertGreaterEqual(offset, -720)
        self.assertLessEqual(offset, 840)


if __name__ == "__main__":
    unittest.main()
