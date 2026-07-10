"""键盘语义与高影响操作策略。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KeyIntent(str, Enum):
    """键盘意图枚举定义"""
    CONFIRM = "confirm"
    TOGGLE_PREVIEW = "toggle_preview"
    BACK = "back"
    HELP = "help"
    GLOBAL_SEARCH = "global_search"
    DANGEROUS_ACTION = "dangerous_action"


@dataclass(frozen=True)
class PendingConfirmation:
    """挂起的待二次确认操作的数据封装"""
    action: str
    prompt: str
    confirm_key: str = "y"
    cancel_key: str = "escape"


# 高影响二次确认提示文案映射
HIGH_IMPACT_ACTIONS = {
    "suspend_word": "再次按 y 挂起该单词，Esc 取消",
    "sync_deck": "再次按 y 同步当前词书，Esc 取消",
    "change_mapping": "再次按 y 修改字段映射，Esc 取消",
}
