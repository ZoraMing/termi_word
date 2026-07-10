"""首页功能快捷键配置与校验。"""
from __future__ import annotations


HOME_ACTIONS = [
    ("study", "学习"),
    ("review", "复习"),
    ("spelling", "拼写"),
    ("words", "词表"),
    ("calendar", "日历"),
    ("settings", "设置"),
]

DEFAULT_HOME_SHORTCUTS = {
    "study": "1",
    "review": "2",
    "spelling": "3",
    "words": "4",
    "calendar": "5",
    "settings": "6",
}


def normalize_shortcut(value: object) -> str:
    """统一快捷键输入格式。"""
    return str(value or "").strip().lower().replace(" ", "")


def home_shortcuts_from_setting(setting) -> dict[str, str]:
    """从设置对象读取首页快捷键，缺失时返回默认值。"""
    result: dict[str, str] = {}
    for action, _label in HOME_ACTIONS:
        attr = f"home_key_{action}"
        result[action] = normalize_shortcut(getattr(setting, attr, None) or DEFAULT_HOME_SHORTCUTS[action])
    return result


def validate_home_shortcuts(shortcuts: dict[str, str], reserved: set[str] | None = None) -> None:
    """校验首页快捷键不能为空、不可重复、不可与保留快捷键冲突。"""
    reserved = {normalize_shortcut(key) for key in (reserved or set()) if key}
    seen: dict[str, str] = {}
    for action, label in HOME_ACTIONS:
        value = normalize_shortcut(shortcuts.get(action))
        if not value:
            raise ValueError(f"【{label}】快捷键不能为空")
        if value in seen:
            raise ValueError(f"快捷键 {value} 同时绑定了【{seen[value]}】和【{label}】")
        if value in reserved:
            raise ValueError(f"快捷键 {value} 已被全局功能占用")
        seen[value] = label


def format_home_menu(shortcuts: dict[str, str]) -> str:
    """生成首页菜单展示文案。"""
    return "  ".join(f"[{shortcuts[action]}]{label}" for action, label in HOME_ACTIONS)


def format_home_help(shortcuts: dict[str, str]) -> str:
    """生成首页帮助提示。"""
    parts = [f"{shortcuts[action]}-{label}" for action, label in HOME_ACTIONS]
    return "快捷键: " + " | ".join(parts) + " | Esc 退出"
