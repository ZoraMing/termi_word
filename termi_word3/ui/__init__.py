"""Termi Word 3 UI 工具函数"""
from __future__ import annotations

import unicodedata

from rich.text import Text

PANEL_WIDTH = 68  # 内容区域标准显示宽度（除去外边框占用的宽度）
PANEL_HEIGHT = 12
MIN_PANEL_HEIGHT = 6
MAX_PANEL_HEIGHT = 16


def display_width(text: str) -> int:
    """计算文本在终端中的实际显示宽度（CJK 宽字符计为 2），支持 Rich markup 过滤。"""
    return Text.from_markup(text).cell_len


def char_width(char: str) -> int:
    if unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F", "A"} else 1


def _pad_to_width(text: str, width: int) -> str:
    """将文本右侧填充空格至指定显示宽度，若以 [/] 结尾，则将空格填充在闭合标签内部以防样式溢出。"""
    current = display_width(text)
    if current >= width:
        return text
    padding = " " * (width - current)
    if text.endswith("[/]"):
        return text[:-3] + padding + "[/]"
    return text + padding


def fit(text: str, width: int) -> str:
    """按显示宽度截断文本，超出部分以 '...' 代替，保留富文本 markup。"""
    t = Text.from_markup(text)
    if t.cell_len <= width:
        return text
    t.truncate(width, overflow="ellipsis")
    return t.markup


def rule(width: int = PANEL_WIDTH) -> str:
    """生成水平分割线 ────────"""
    return "─" * (width // 2)


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


def truncate_display(text: str, width: int = PANEL_WIDTH) -> str:
    if width <= 0:
        return ""
    if width <= 3:
        return text if display_width(text) <= width else "." * width
    if display_width(text) <= width:
        return text
    result = ""
    used = 0
    for char in text:
        current_width = char_width(char)
        if used + current_width > width - 3:
            break
        result += char
        used += current_width
    return result + "..."


def pad_display(text: str, width: int = PANEL_WIDTH) -> str:
    return text + " " * max(0, width - display_width(text))


def wrap_display(text: str, width: int = PANEL_WIDTH, continuation_indent: str = "") -> list[str]:
    if width <= 0:
        return [""]
    if display_width(text) <= width:
        return [text]
    result: list[str] = []
    current = ""
    current_width = 0
    indent_width = display_width(continuation_indent)
    for char in text:
        cw = char_width(char)
        if current and current_width + cw > width:
            result.append(current)
            current = continuation_indent
            current_width = indent_width
        current += char
        current_width += cw
    if current:
        result.append(current)
    return result or [""]


def wrap_lines(lines: list[str], width: int = PANEL_WIDTH, continuation_indent: str = "") -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if line == "":
            wrapped.append("")
            continue
        wrapped.extend(wrap_display(line, width, continuation_indent))
    return wrapped


def footer_lines(text: str, width: int = PANEL_WIDTH, max_lines: int = 2) -> list[str]:
    """将底部快捷键提示按终端显示宽度折行，避免窄窗口直接截断。"""
    lines = wrap_display(text, width)
    return lines[: max(1, max_lines)]


def footer_height(text: str, width: int = PANEL_WIDTH, max_lines: int = 2) -> int:
    return len(footer_lines(text, width, max_lines))


def render_footer(text: str, width: int = PANEL_WIDTH, max_lines: int = 2) -> str:
    return "\n".join(footer_lines(text, width, max_lines))


def panel_height(
    terminal_height: int,
    min_height: int = MIN_PANEL_HEIGHT,
    max_height: int = MAX_PANEL_HEIGHT,
) -> int:
    max_height = max(1, max_height)
    min_height = max(1, min(min_height, max_height))
    return max(min_height, min(max_height, terminal_height))


def panel_width(terminal_width: int, max_width: int = PANEL_WIDTH) -> int:
    available = max(1, terminal_width - 8)
    return max(1, min(available, max(1, max_width)))


def panel_body_height(height: int) -> int:
    return max(1, height - 2)


def scroll_window(lines: list[str], height: int, offset: int) -> list[str]:
    if height <= 0:
        return []
    offset = max(0, min(offset, max(0, len(lines) - height)))
    visible = lines[offset : offset + height]
    while len(visible) < height:
        visible.append("")
    return visible


def clamp_scroll_offset(lines_count: int, height: int, offset: int) -> int:
    if height <= 0:
        return 0
    return max(0, min(offset, max(0, lines_count - height)))


PanelLine = str | Text


def append_line(text: Text, line: PanelLine, width: int = PANEL_WIDTH) -> None:
    if isinstance(line, Text):
        text.append_text(truncate_text(line, width))
    else:
        text.append(truncate_display(line, width))


def truncate_text(value: Text, width: int = PANEL_WIDTH) -> Text:
    result = value.copy()
    result.truncate(width, overflow="ellipsis")
    return result


def text_panel(
    title: str,
    lines: list[PanelLine],
    footer: str,
    height: int,
    status: str = "",
    width: int = PANEL_WIDTH,
) -> Text:
    body_height = panel_body_height(height)
    visible = scroll_window(lines, body_height, 0)
    text = Text()
    head = f"{title} {status}".strip()
    text.append(truncate_display(head, width), style="bold")
    text.append("\n")
    for line in visible[:-1]:
        append_line(text, line, width)
        text.append("\n")
    if visible:
        append_line(text, visible[-1], width)
        text.append("\n")
    text.append(truncate_display(footer, width), style="#9ca3af")
    return text


def rating_label(rating: int) -> str:
    return {1: "陌生", 2: "熟悉", 3: "记得", 4: "掌握"}.get(rating, "未评分")


from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

class TermiScreen(Screen):
    """Termi Word 统一界面基类，负责 Header, Content, Message, Footer 整体布局与样式的架构化收管。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_header = ""
        self._last_lines: list[str] = []
        self._last_message = ""
        self._last_footer = ""
        self._msg_severity = "info"

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def refresh_ui(
        self,
        header: str | None = None,
        lines: list[str] | None = None,
        message: str | None = None,
        footer: str | None = None,
        severity: str = "info",
    ) -> None:
        """一站式刷新界面的 Header, Content, Message, Footer，支持局部增量更新。"""
        if header is not None:
            self._last_header = header
        if lines is not None:
            self._last_lines = lines
        if message is not None:
            self._last_message = message
        self._msg_severity = severity
        if footer is not None:
            self._last_footer = footer

        self.draw_frame()

    def draw_frame(self) -> None:
        """渲染绘制核心。进行动态布局裁剪与 Widget 更新。"""
        try:
            content_widget = self.query_one("#content-area", Static)
            msg_widget = self.query_one("#message-area", Static)
            footer_widget = self.query_one("#footer-area", Static)
        except Exception:
            return  # 组件尚未就绪

        # 1. 动态高度计算
        content_height, width = self.compute_dynamic_layout()

        # 2. 组装 Content 内容：Header + 分割线 + 主体 lines
        final_lines = []
        if self._last_header:
            final_lines.append(self._last_header)
            final_lines.append(rule(width))

        final_lines.extend(self._last_lines)

        # 3. 填充与截断
        rendered_content = render_content_block(final_lines, height=content_height, width=width)
        content_widget.update(rendered_content)

        # 4. 更新消息区
        msg_widget.remove_class("success", "error", "muted")
        if self._msg_severity != "info":
            msg_widget.add_class(self._msg_severity)
        else:
            msg_widget.add_class("muted")
        msg_widget.update(self._last_message)

        # 5. 更新页脚
        footer_widget.update(render_footer(self._last_footer, width))

    def compute_dynamic_layout(self) -> tuple[int, int]:
        # 自动探测是否有 Input 输入框
        from textual.widgets import Input
        has_input = False
        try:
            self.query_one(Input)
            has_input = True
        except Exception:
            pass

        with self.app.session_factory() as session:
            from termi_word3.database.repositories import AppRepository
            setting = AppRepository(session).get_settings()
            
        from termi_word3.ui.layout import compute_frame_layout
        layout = compute_frame_layout(
            terminal_width=self.size.width,
            terminal_height=self.size.height,
            panel_min_height=setting.panel_min_height,
            panel_max_height=setting.panel_max_height,
            panel_max_width=setting.panel_max_width,
            footer_text=self._last_footer,
            has_input=has_input,
            message_rows=1,
        )
        
        # 统一应用样式布局
        container = self.query_one(".frame-container", Static)
        container.styles.height = layout.frame_height
        container.styles.min_height = layout.frame_height
        container.styles.max_height = layout.frame_height
        container.styles.width = layout.frame_width
        
        self.query_one("#footer-area", Static).styles.height = layout.footer_rows

        content = self.query_one("#content-area", Static)
        content.styles.height = layout.content_height
        content.styles.min_height = layout.content_height
        content.styles.max_height = layout.content_height
        
        return layout.content_height, layout.content_width

    def on_resize(self) -> None:
        """全屏尺寸变化自动响应重绘。"""
        self.draw_frame()
