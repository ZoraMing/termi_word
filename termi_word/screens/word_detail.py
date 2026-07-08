from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from termi_word.ui import panel_height, scroll_window, text_panel


class WordDetailScreen(Screen):
    BINDINGS = [("escape", "back", "返回"), ("up", "scroll_up", "上"), ("down", "scroll_down", "下")]

    def __init__(self, word_id: int) -> None:
        super().__init__()
        self.word_id = word_id
        self.detail_view_offset = 0

    def compose(self) -> ComposeResult:
        yield Static(id="word-detail", classes="panel")

    def on_mount(self) -> None:
        self.render_panel()

    def render_panel(self) -> None:
        height = panel_height(self.size.height)
        word = self.app.search_service.word_detail(self.word_id)
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
        body_height = max(1, height - 2)
        self.query_one("#word-detail", Static).update(
            text_panel("单词详情", scroll_window(lines, body_height, self.detail_view_offset), "↑↓ 滚动  Esc 返回", height)
        )

    def action_scroll_up(self) -> None:
        self.detail_view_offset = max(0, self.detail_view_offset - 1)
        self.render_panel()

    def action_scroll_down(self) -> None:
        self.detail_view_offset += 1
        self.render_panel()

    def action_back(self) -> None:
        self.app.pop_screen()
