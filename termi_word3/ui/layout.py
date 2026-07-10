"""Textual Frame 布局计算。"""
from __future__ import annotations

from dataclasses import dataclass

from termi_word3.ui import footer_height, panel_height, panel_width


@dataclass(frozen=True)
class FrameLayout:
    """布局计算结果的数据结构封装"""
    frame_height: int
    frame_width: int
    content_height: int
    content_width: int
    footer_rows: int
    message_rows: int


def compute_frame_layout(
    terminal_width: int,
    terminal_height: int,
    panel_min_height: int,
    panel_max_height: int,
    panel_max_width: int,
    footer_text: str,
    has_input: bool = False,
    message_rows: int = 1,
) -> FrameLayout:
    """统一计算 Termi Word 界面的容器高度、内容宽度、页脚高度和主体高度。"""
    frame_height = panel_height(terminal_height, panel_min_height, panel_max_height)
    frame_width = panel_width(terminal_width, panel_max_width)
    content_width = max(1, frame_width - 2)
    footer_rows = footer_height(footer_text, content_width)
    input_rows = 1 if has_input else 0
    # 容器边框(2) + 输入框行数 + 消息行数 + 页脚行数
    content_height = max(3, frame_height - 2 - input_rows - message_rows - footer_rows)
    return FrameLayout(
        frame_height=frame_height,
        frame_width=frame_width,
        content_height=content_height,
        content_width=content_width,
        footer_rows=footer_rows,
        message_rows=message_rows,
    )
