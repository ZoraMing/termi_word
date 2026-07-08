"""加载 Footer 按键配置"""
from __future__ import annotations

import json
from pathlib import Path
from termi_word3.config import DATA_DIR

DEFAULT_UI_CONFIG = {
    "footer": {
        "today": "1-7 跳转   Ctrl+/ 搜索   Esc Esc 退出",
        "words": "上下 移动   Space/Enter 详情   Esc 返回",
        "calendar": "上下 选择   Enter/Space 编辑   Esc 返回",
        "settings": "上下 选择   Enter/Space 确认   Esc 返回",
        "review": "Space 翻卡   1-4 评分   f 收藏   t 挂起   Esc 返回",
        "spelling": "Enter 提交   Tab 提示   Space 答案   s 跳过   Esc 返回",
    }
}


class UiConfigService:
    """提供各页面 Footer 的快捷键提示。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DATA_DIR / "ui_config.json"

    def load(self) -> dict:
        """从 JSON 配置文件加载配置。若不存在则生成默认配置。"""
        if not self.path.exists():
            self.save(DEFAULT_UI_CONFIG)
            return dict(DEFAULT_UI_CONFIG)
        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            merged = dict(DEFAULT_UI_CONFIG)
            merged["footer"] = {**DEFAULT_UI_CONFIG["footer"], **data.get("footer", {})}
            return merged
        except Exception:
            return dict(DEFAULT_UI_CONFIG)

    def save(self, config: dict) -> None:
        """保存配置到本地。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=2)

    def footer(self, key: str) -> str:
        """获取指定页面的 Footer 快捷键提示串。"""
        return self.load().get("footer", {}).get(key, "")
