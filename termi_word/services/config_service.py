from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from termi_word.config import DEFAULT_DAILY_NEW_TARGET, DEFAULT_DECK_NAME, DEFAULT_REVIEW_SOFT_LIMIT, UI_CONFIG_PATH


@dataclass(frozen=True)
class AppConfig:
    active_deck: str
    daily_new_target: int
    review_soft_limit: int
    daily_spelling_target: int
    spelling_enabled: bool
    theme: str
    footer: dict[str, str]
    import_start_row: int
    import_end_row: int


DEFAULT_CONFIG = {
    "active_deck": DEFAULT_DECK_NAME,
    "daily_new_target": DEFAULT_DAILY_NEW_TARGET,
    "review_soft_limit": DEFAULT_REVIEW_SOFT_LIMIT,
    "daily_spelling_target": 15,
    "spelling_enabled": True,
    "theme": "quiet_dark",
    "import_start_row": 1,
    "import_end_row": 0,
    "footer": {
        "today": "1 学习  2 复习  Ctrl+P 搜索",
        "review_front": "1-4 初评  s 跳过  Esc 返回",
        "review_back": "1-4 修正  Enter 确认",
        "search": "Enter 查看  Esc 返回",
        "calendar": "Esc 返回",
        "settings": "↑↓ 选择  Enter 编辑  Esc 返回",
        "spelling": "Enter 提交  Tab 提示  Space 答案",
    },
}


class ConfigService:
    def __init__(self, path: Path = UI_CONFIG_PATH) -> None:
        self.path = path
        self._cache: AppConfig | None = None

    def load(self) -> AppConfig:
        if self._cache is not None:
            return self._cache
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        data = DEFAULT_CONFIG | json.loads(self.path.read_text(encoding="utf-8"))
        footer = DEFAULT_CONFIG["footer"] | dict(data.get("footer") or {})
        footer = {key: value.replace("Ctrl+/", "Ctrl+P") for key, value in footer.items()}
        self._cache = AppConfig(
            active_deck=str(data.get("active_deck") or DEFAULT_DECK_NAME),
            daily_new_target=max(0, int(data.get("daily_new_target") or DEFAULT_DAILY_NEW_TARGET)),
            review_soft_limit=max(0, int(data.get("review_soft_limit") or DEFAULT_REVIEW_SOFT_LIMIT)),
            daily_spelling_target=max(0, int(data.get("daily_spelling_target") or 15)),
            spelling_enabled=bool(data.get("spelling_enabled", True)),
            theme=str(data.get("theme") or "quiet_dark"),
            footer=footer,
            import_start_row=max(1, int(data.get("import_start_row") or 1)),
            import_end_row=max(0, int(data.get("import_end_row") or 0)),
        )
        return self._cache

    def save_values(self, values: dict[str, int | bool | str]) -> AppConfig:
        current = DEFAULT_CONFIG | {}
        if self.path.exists():
            current |= json.loads(self.path.read_text(encoding="utf-8"))
        current.update(values)
        current["footer"] = DEFAULT_CONFIG["footer"] | dict(current.get("footer") or {})
        self.path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cache = None
        return self.load()
