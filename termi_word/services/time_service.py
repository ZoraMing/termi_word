"""本地业务时间配置。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from termi_word.config import DATA_DIR


LOCAL_TIME_CONFIG_PATH = DATA_DIR / "local_time.json"
_OFFSET_RE = re.compile(r"^([+-])(\d{2}):(\d{2})$")


@dataclass(frozen=True)
class LocalTimeConfig:
    """本地业务时间配置快照。"""

    timezone_offset_minutes: int


def system_timezone_offset_minutes(now: datetime | None = None) -> int:
    """读取当前系统时区相对 UTC 的分钟偏移。"""
    local_now = now or datetime.now().astimezone()
    offset = local_now.utcoffset() or timedelta()
    return int(offset.total_seconds() // 60)


def parse_offset(value: str) -> int:
    """解析 '+08:00' / '-05:30' 格式为分钟偏移。"""
    match = _OFFSET_RE.match(value.strip())
    if not match:
        raise ValueError("时区偏移格式应为 +08:00 或 -05:00")
    sign, hours, minutes = match.groups()
    total = int(hours) * 60 + int(minutes)
    if int(hours) > 14 or int(minutes) >= 60:
        raise ValueError("时区偏移超出有效范围")
    return total if sign == "+" else -total


def format_offset(offset_minutes: int) -> str:
    """将分钟偏移格式化为 '+08:00'。"""
    sign = "+" if offset_minutes >= 0 else "-"
    minutes_abs = abs(int(offset_minutes))
    hours, minutes = divmod(minutes_abs, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def timezone_from_offset(offset_minutes: int) -> timezone:
    """根据分钟偏移构造固定时区对象。"""
    return timezone(timedelta(minutes=int(offset_minutes)))


class TimeSettingsService:
    """启动时校验本地时间配置文件。"""

    def __init__(
        self,
        config_path: Path = LOCAL_TIME_CONFIG_PATH,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.config_path = config_path
        self.now = now or (lambda: datetime.now().astimezone())

    def ensure_config(self) -> LocalTimeConfig:
        """确保本地时区配置存在；已存在时不覆盖用户修改。"""
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            return LocalTimeConfig(int(data.get("timezone_offset_minutes", 0)))

        config = LocalTimeConfig(system_timezone_offset_minutes(self.now()))
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "timezone_offset_minutes": config.timezone_offset_minutes,
                    "timezone_offset": format_offset(config.timezone_offset_minutes),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return config

    def save_config(self, offset_minutes: int) -> LocalTimeConfig:
        """保存用户在设置页修改后的本地时区配置。"""
        config = LocalTimeConfig(int(offset_minutes))
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "timezone_offset_minutes": config.timezone_offset_minutes,
                    "timezone_offset": format_offset(config.timezone_offset_minutes),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return config
