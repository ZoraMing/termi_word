from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from termi_word.ui import panel_height, text_panel


class TodoScreen(Screen):
    BINDINGS = [("escape", "back", "返回")]

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self.todo_title = title
        self.message = message

    def compose(self) -> ComposeResult:
        yield Static(id="todo-panel", classes="panel")

    def on_mount(self) -> None:
        self.render_panel()

    def render_panel(self) -> None:
        height = panel_height(self.size.height)
        self.query_one("#todo-panel", Static).update(
            text_panel(self.todo_title, [self.message, "", "TODO: 后续阶段实现。"], "Esc 返回", height)
        )

    def action_back(self) -> None:
        self.app.pop_screen()
