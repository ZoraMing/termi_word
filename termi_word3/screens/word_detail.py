"""单词详情展示屏幕"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static

from termi_word3.database.repositories import AppRepository
from termi_word3.ui import (
    clamp_scroll_offset,
    panel_body_height,
    panel_height,
    panel_width,
    scroll_window,
    text_panel,
    wrap_lines,
)
from termi_word3.ui.layout import compute_frame_layout


class WordDetailScreen(Screen):
    """单词详情展示屏幕"""

    BINDINGS = [("escape", "back", "返回"), ("up", "scroll_up", "上"), ("down", "scroll_down", "下")]

    def __init__(self, word_id: int) -> None:
        super().__init__()
        self.word_id = word_id
        self.detail_view_offset = 0

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def apply_dynamic_layout(self) -> tuple[int, int]:
        with self.app.session_factory() as session:
            setting = AppRepository(session).get_settings()
        
        layout = compute_frame_layout(
            terminal_width=self.size.width,
            terminal_height=self.size.height,
            panel_min_height=setting.panel_min_height,
            panel_max_height=setting.panel_max_height,
            panel_max_width=setting.panel_max_width,
            footer_text="",
            has_input=False,
            message_rows=0,
        )
        
        container = self.query_one(".frame-container", Static)
        container.styles.height = layout.frame_height
        container.styles.min_height = layout.frame_height
        container.styles.max_height = layout.frame_height
        container.styles.width = layout.frame_width
        
        content = self.query_one("#content-area", Static)
        content.styles.height = layout.content_height
        content.styles.min_height = layout.content_height
        content.styles.max_height = layout.content_height
        
        return layout.frame_height, layout.frame_width

    def on_resize(self) -> None:
        """窗口缩放事件，重新刷新渲染页面。"""
        self.render_panel()

    def on_key(self, event: Key) -> None:
        """全局键盘逻辑拦截。"""
        if self.app.is_search_shortcut(event.key):
            event.stop()
            self.app.open_search()
            return

    def on_mount(self) -> None:
        self.render_panel()

    def render_panel(self) -> None:
        height, width = self.apply_dynamic_layout()

        with self.app.session_factory() as session:
            from termi_word3.database.repositories import AppRepository
            repo = AppRepository(session)
            word = repo.get_word_by_id(self.word_id)

        if word is None:
            lines = ["单词不存在"]
        else:
            lines = [
                f"{word.w}  {word.us or ''}  [{word.c or '-'}]",
                f"核心释义：{word.core}" if word.core else "",
                f"中文释义：{word.zh}" if word.zh else "",
                f"英文定义：{word.en}" if word.en else "",
                f"例句：{word.ex}" if word.ex else "",
                f"翻译：{word.exz}" if word.exz else "",
            ]
            lines = [line for line in lines if line]

        body_height = panel_body_height(height)
        lines = wrap_lines(lines, width, "  ")
        self.detail_view_offset = clamp_scroll_offset(len(lines), body_height, self.detail_view_offset)
        self.query_one("#content-area", Static).update(
            text_panel(
                "单词详情",
                scroll_window(lines, body_height, self.detail_view_offset),
                "↑↓ 滚动  Esc 返回",
                height,
                width=width,
            )
        )

    def action_scroll_up(self) -> None:
        self.detail_view_offset = max(0, self.detail_view_offset - 1)
        self.render_panel()

    def action_scroll_down(self) -> None:
        self.detail_view_offset += 1
        self.render_panel()

    def action_back(self) -> None:
        self.app.pop_screen()
