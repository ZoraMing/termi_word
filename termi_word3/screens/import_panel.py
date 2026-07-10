"""导入词表的预览与选择屏幕"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static

from termi_word3.services.import_service import ImportRow
from termi_word3.ui import clamp_scroll_offset, panel_body_height, panel_height, panel_width, scroll_window, text_panel, truncate_display
from termi_word3.ui.messages import format_import_result


class ImportScreen(Screen):
    """导入词表的预览与选择屏幕"""

    BINDINGS = [("escape", "back", "返回")]

    def __init__(self, deck_name: str) -> None:
        super().__init__()
        self.deck_name = deck_name
        self.source_path = None
        self.rows: list[ImportRow] = []
        self.missing_fields: tuple[str, ...] = ()
        self.skip_rows: set[int] = set()
        self.selected = 0
        self.row_offset = 0
        self.message = ""

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.reload_source()
        self.render_panel()

    def reload_source(self) -> None:
        self.source_path, self.rows, self.missing_fields = self.app.import_service.read_source_rows(self.deck_name)
        self.selected = 0
        self.row_offset = 0

    def on_key(self, event: Key) -> None:
        if self.missing_fields:
            if event.key == "escape":
                event.stop()
                self.action_back()
            return

        if event.key == "up":
            event.stop()
            self.move(-1)
        elif event.key == "down":
            event.stop()
            self.move(1)
        elif event.key == "space":
            event.stop()
            self.toggle_skip()
        elif event.key in {"enter", "return"}:
            event.stop()
            self.import_rows()

    def move(self, delta: int) -> None:
        if not self.rows:
            return
        self.selected = max(0, min(len(self.rows) - 1, self.selected + delta))
        visible_count = self.visible_row_count()
        if self.selected < self.row_offset:
            self.row_offset = self.selected
        elif self.selected >= self.row_offset + visible_count:
            self.row_offset = self.selected - visible_count + 1
        self.render_panel()

    def toggle_skip(self) -> None:
        if not self.rows:
            return
        row_number = self.rows[self.selected].row_number
        if row_number in self.skip_rows:
            self.skip_rows.remove(row_number)
            self.message = f"已恢复第 {row_number} 行"
        else:
            self.skip_rows.add(row_number)
            self.message = f"已跳过第 {row_number} 行"
        self.render_panel()

    def import_rows(self) -> None:
        result = self.app.import_service.import_rows(self.deck_name, self.skip_rows)
        self.message = format_import_result(result)
        self.render_panel()

    def visible_row_count(self) -> int:
        return max(1, panel_body_height(self.panel_height()) - 4)

    def row_lines(self) -> list[str]:
        lines: list[str] = []
        width = self.content_width()
        for row in self.rows:
            marker = "> " if row.row_number == self.current_row_number else "  "
            state = "[跳过]" if row.row_number in self.skip_rows else "[导入]"
            preview = "  ".join(
                part
                for part in [
                    f"{row.row_number:>4}",
                    state,
                    row.values.get("w", ""),
                    row.values.get("c", ""),
                    row.values.get("zh", ""),
                ]
                if part
            )
            lines.append(truncate_display(f"{marker}{preview}", width))
        return lines

    @property
    def current_row_number(self) -> int:
        if not self.rows:
            return 0
        return self.rows[self.selected].row_number

    def render_panel(self) -> None:
        height = self.panel_height()
        width = self.content_width()
        footer = "↑↓ 选择  Space 跳过/恢复  Enter 导入  Esc 返回"
        if self.missing_fields:
            lines = [
                f"词书      {self.deck_name}",
                f"来源      {self.source_path}",
                f"状态      词表字段缺失：{', '.join(self.missing_fields)}",
            ]
            self.query_one("#content-area", Static).update(text_panel("导入词表", lines, "Esc 返回", height, width=width))
            return

        header = [
            f"词书      {self.deck_name}",
            f"来源      {self.source_path.name if self.source_path else '-'}",
            f"预览      {len(self.rows)} 行  跳过 {len(self.skip_rows)} 行",
        ]
        message_height = 2 if self.message else 0
        row_height = max(1, panel_body_height(height) - len(header) - 1 - message_height)
        self.row_offset = clamp_scroll_offset(len(self.rows), row_height, self.row_offset)
        row_lines = scroll_window(self.row_lines(), row_height, self.row_offset)
        lines = [*header, "", *row_lines]
        if self.message:
            lines.append("")
            lines.append(self.message)
        self.query_one("#content-area", Static).update(text_panel("导入词表", lines, footer, height, width=width))

    def action_back(self) -> None:
        self.app.pop_screen()

    def content_width(self) -> int:
        return panel_width(self.size.width, 68)

    def panel_height(self) -> int:
        return panel_height(self.size.height, 6, 16)
