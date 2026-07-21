"""加载 Footer 按键配置"""
from __future__ import annotations

import json
from typing import Callable

# 默认模板：代码中定义，首次运行时导入数据库
DEFAULT_FOOTER_CONFIG = {
    "today": "Ctrl+/ 搜索   Esc Esc 退出",
    "words": "↑↓ 选词   Space/Enter 锁定详情   Esc 返回",
    "calendar": "↑↓ 选择目标   Enter/Space 修改   Esc 返回",
    "settings": "↑↓ 选择字段   Enter/Space 修改   Esc 返回",
    "review": "Space 翻卡   1-4 评分   t 挂起   f 收藏   Esc 返回",
    "spelling": "Enter 提交   Tab 提示   Space 答案   s 跳过   Esc 返回",
}


class UiConfigService:
    """提供各页面 Footer 的快捷键提示，数据存储在数据库。"""

    def __init__(self, session_factory: Callable | None = None) -> None:
        self._session_factory = session_factory

    def _get_session_factory(self):
        """获取数据库会话工厂。"""
        if self._session_factory is not None:
            return self._session_factory
        from termi_word.database.engine import get_session_factory
        return get_session_factory()

    def load(self) -> dict:
        """从数据库加载 footer 配置。若不存在则使用默认模板。"""
        from termi_word.database.repositories import AppRepository

        session_factory = self._get_session_factory()
        with session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()

            # 如果数据库中没有 footer 配置，使用默认模板并保存
            if not setting.footer:
                setting.footer = json.dumps(DEFAULT_FOOTER_CONFIG, ensure_ascii=False)
                session.commit()
                return {"footer": dict(DEFAULT_FOOTER_CONFIG)}

            try:
                footer = json.loads(setting.footer)
                # 合并默认配置，确保新增的页面有默认值
                merged = {**DEFAULT_FOOTER_CONFIG, **footer}
                return {"footer": merged}
            except (json.JSONDecodeError, TypeError):
                return {"footer": dict(DEFAULT_FOOTER_CONFIG)}

    def save(self, config: dict) -> None:
        """保存 footer 配置到数据库。"""
        from termi_word.database.repositories import AppRepository

        session_factory = self._get_session_factory()
        with session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            setting.footer = json.dumps(config.get("footer", {}), ensure_ascii=False)
            session.commit()

    def footer(self, key: str) -> str:
        """获取指定页面的 Footer 快捷键提示串。"""
        return self.load().get("footer", {}).get(key, "")
