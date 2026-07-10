"""全局设置数据存取仓储。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from termi_word.database.models import Setting


class SettingsRepository:
    """负责全局系统设置行的查询和保存"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self) -> Setting:
        """获取或创建唯一的全局设置行"""
        setting = self.session.execute(select(Setting).order_by(Setting.id)).scalars().first()
        if setting is None:
            setting = Setting()
            self.session.add(setting)
            self.session.flush()
        return setting

    def save(self, setting: Setting) -> None:
        """保存或刷新设置状态"""
        self.session.flush()
