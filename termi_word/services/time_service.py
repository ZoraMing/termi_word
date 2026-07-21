"""本地业务时间配置。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

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
    """时区配置服务，数据存储在数据库。"""

    def __init__(
        self,
        session_factory: Callable | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.now = now or (lambda: datetime.now().astimezone())

    def _get_session_factory(self):
        """获取数据库会话工厂。"""
        if self._session_factory is not None:
            return self._session_factory
        from termi_word.database.engine import get_session_factory
        return get_session_factory()

    def ensure_config(self) -> LocalTimeConfig:
        """确保本地时区配置存在；已存在时不覆盖用户修改。"""
        from termi_word.database.repositories import AppRepository

        session_factory = self._get_session_factory()
        with session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()

            # 如果数据库中已有配置，直接返回
            if setting.timezone_offset_minutes is not None:
                return LocalTimeConfig(setting.timezone_offset_minutes)

            # 首次运行：检测系统时区并保存
            offset = system_timezone_offset_minutes(self.now())
            setting.timezone_offset_minutes = offset
            session.commit()
            return LocalTimeConfig(offset)

    def save_config(self, offset_minutes: int) -> LocalTimeConfig:
        """保存用户在设置页修改后的本地时区配置。"""
        from termi_word.database.repositories import AppRepository

        config = LocalTimeConfig(int(offset_minutes))

        session_factory = self._get_session_factory()
        with session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            setting.timezone_offset_minutes = config.timezone_offset_minutes
            session.commit()

        return config
