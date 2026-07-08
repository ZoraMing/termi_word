from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static
from rich.text import Text

from termi_word.services.search_service import SearchEntry
from termi_word.ui import panel_height, scroll_window, text_panel


class SearchScreen(Screen):
    BINDINGS = [("escape", "back", "返回")]

    def __init__(self, deck_name: str) -> None:
        super().__init__()
        self.deck_name = deck_name
        self.search_text = ""
        self.selected = 0
        self.result_offset = 0
        self.detail_entry: SearchEntry | None = None
        self.results: list[SearchEntry] = []

    def compose(self) -> ComposeResult:
        yield Static(id="search-panel", classes="panel")

    def on_mount(self) -> None:
        self.results = self.app.search_service.search(self.deck_name, "", 100)
        self.render_panel()

    def on_key(self, event: Key) -> None:
        if event.key == "ctrl+p":
            event.stop()
            return
        if event.key in {"ctrl+z", "escape"}:
            return
        event.stop()
        if event.key == "up":
            self.move(-1)
        elif event.key == "down":
            self.move(1)
        elif event.key in {"enter", "space"}:
            self.select_current()
        elif event.key == "backspace":
            self.search_text = self.search_text[:-1]
            self.apply_filter()
        elif len(event.character or "") == 1:
            self.search_text += event.character
            self.apply_filter()

    def apply_filter(self) -> None:
        query = self.search_text.strip().lower()
        self.detail_entry = None
        self.results = self.app.search_service.search(self.deck_name, query, 100)
        self.selected = 0
        self.result_offset = 0
        self.render_panel()

    def move(self, delta: int) -> None:
        if not self.results:
            return
        self.selected = max(0, min(len(self.results) - 1, self.selected + delta))
        if self.selected < self.result_offset:
            self.result_offset = self.selected
        visible_count = self.visible_result_count()
        if self.selected >= self.result_offset + visible_count:
            self.result_offset = self.selected - visible_count + 1
        self.render_panel()

    def select_current(self) -> None:
        if not self.results:
            return
        self.detail_entry = self.results[self.selected]
        self.render_panel()

    def render_panel(self) -> None:
        height = panel_height(self.size.height)
        lines = [
            f"结果      {len(self.results)}",
            f"选中      {self.current_title()}",
            self.input_line(),
        ]
        if self.detail_entry is not None:
            lines.extend(self.detail_lines(self.detail_entry))
        else:
            visible = self.results[self.result_offset : self.result_offset + self.visible_result_count()]
            for index, entry in enumerate(visible, start=self.result_offset):
                marker = "> " if index == self.selected else "  "
                line = f"{marker}{entry.title:<18} {entry.detail}"
                lines.append(self.accent_line(line) if index == self.selected else line)
            if not visible:
                lines.append("  无匹配结果")
        self.query_one("#search-panel", Static).update(
            text_panel("搜索", scroll_window(lines, max(1, height - 1), 0), "↑↓ 选择  Enter/Space 展示  Esc 返回", height)
        )

    def visible_result_count(self) -> int:
        return 5

    def current_title(self) -> str:
        if not self.results:
            return "-"
        entry = self.results[self.selected]
        return f"{entry.title}  {entry.detail}"

    def detail_lines(self, entry: SearchEntry) -> list[str]:
        return ["", *entry.lines, "Enter/Space 保持展示，输入新内容重新筛选"]

    def input_line(self) -> Text:
        text = Text()
        text.append("> ", style="orange1 bold")
        text.append(self.search_text or "输入单词或释义", style="orange1")
        return text

    def accent_line(self, value: str) -> Text:
        text = Text()
        text.append(value, style="orange1")
        return text

    def action_back(self) -> None:
        self.app.pop_screen()
