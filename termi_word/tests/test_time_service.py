"""本地时区配置服务测试。"""
from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path

from termi_word.services.time_service import TimeSettingsService, format_offset, parse_offset


class TestTimeSettingsService(unittest.TestCase):
    """验证启动时区校验和设置页可编辑格式。"""

    def test_parse_and_format_timezone_offset(self) -> None:
        self.assertEqual(parse_offset("+08:00"), 480)
        self.assertEqual(parse_offset("-05:30"), -330)
        self.assertEqual(format_offset(480), "+08:00")
        self.assertEqual(format_offset(-330), "-05:30")

    def test_ensure_config_writes_detected_offset_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local_time.json"
            service = TimeSettingsService(
                config_path=path,
                now=lambda: datetime.datetime(
                    2026,
                    7,
                    10,
                    8,
                    0,
                    tzinfo=datetime.timezone(datetime.timedelta(hours=8)),
                ),
            )

            first = service.ensure_config()
            path.write_text(json.dumps({"timezone_offset_minutes": 60}), encoding="utf-8")
            second = service.ensure_config()

            self.assertEqual(first.timezone_offset_minutes, 480)
            self.assertEqual(second.timezone_offset_minutes, 60)
