"""Termi Word 3 UI 工具函数"""
from __future__ import annotations

import unicodedata

PANEL_WIDTH = 68  # 内容区域标准显示宽度（除去外边框占用的宽度）
PANEL_HEIGHT = 12

def display_width(text: str) -> int:
    """计算文本在终端中的实际显示宽度（CJK 宽字符计为 2）。"""
    width = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        width += 2 if eaw in ("W", "F") else 1
    return width


def _pad_to_width(text: str, width: int) -> str:
    """将文本右侧填充空格至指定显示宽度。"""
    current = display_width(text)
    if current >= width:
        return text
    return text + " " * (width - current)


def fit(text: str, width: int) -> str:
    """按显示宽度截断文本，超出部分以 '...' 代替。"""
    if display_width(text) <= width:
        return text
    ellipsis = "..."
    target = width - len(ellipsis)
    if target < 0:
        target = 0
    result = []
    current = 0
    for ch in text:
        ch_w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if current + ch_w > target:
            break
        result.append(ch)
        current += ch_w
    return "".join(result) + ellipsis


def rule(width: int = PANEL_WIDTH) -> str:
    """生成水平分割线 ────────"""
    return "─" * width


def field_row(
    label: str,
    value: object,
    selected: bool = False,
    editing: bool = False,
    width: int = 14,
) -> str:
    """格式化展示带选择和编辑标记的字段行。
    > 表示当前选中，>_ 表示编辑状态。
    """
    prefix = ">_" if editing else ("> " if selected else "  ")
    label_padded = _pad_to_width(label, width)
    return f"{prefix}{label_padded} {value}"


def render_content_block(lines: list[str], height: int, width: int = PANEL_WIDTH) -> str:
    """将文本行格式化并截断/填充到指定行数与宽度，以 \n 连接。"""
    result = []
    for line in lines[:height]:
        fitted = fit(line, width)
        result.append(_pad_to_width(fitted, width))
    while len(result) < height:
        result.append(" " * width)
    return "\n".join(result)
