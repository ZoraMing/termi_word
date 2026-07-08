from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static
from rich.text import Text

from termi_word.database.models import Word
from termi_word.ui import panel_height, text_panel


class SpellingScreen(Screen):
    BINDINGS = [("escape", "back", "返回")]

    def __init__(self, words: list[Word], message: str = "") -> None:
        super().__init__()
        self.words = words
        self.index = 0
        self.input_value = ""
        self.hints = 0
        self.show_answer = False
        self.awaiting_next = False
        self.message = message

    def compose(self) -> ComposeResult:
        yield Static(id="spelling-panel", classes="panel")

    def on_mount(self) -> None:
        self.render_panel()

    @property
    def current_word(self) -> Word | None:
        if self.index >= len(self.words):
            return None
        return self.words[self.index]

    def on_key(self, event: Key) -> None:
        word = self.current_word
        if word is None:
            return
        if event.key in {"ctrl+z", "ctrl+p", "escape"}:
            return
        event.stop()
        if self.awaiting_next:
            if event.key in {"enter", "space"}:
                self.next_word("")
            return
        if event.key == "enter":
            self.submit()
        elif event.key == "tab":
            self.hint()
        elif event.key == "space":
            self.show_answer = True
            self.render_panel()
        elif event.key == "backspace":
            self.input_value = self.input_value[:-1]
            self.render_panel()
        elif event.key == "s" and not self.input_value:
            self.next_word("已跳过")
        elif len(event.character or "") == 1 and event.character.isalpha():
            if len(self.input_value) < len(word.w):
                self.input_value += event.character
                self.show_answer = False
                self.render_panel()

    def submit(self) -> None:
        word = self.current_word
        if word is None:
            return
        result = self.app.spelling_service.submit(word.id, self.input_value, self.hints)
        self.message = result.message
        self.show_answer = True
        self.awaiting_next = True
        self.render_panel()

    def hint(self) -> None:
        word = self.current_word
        if word is None:
            return
        self.input_value = word.w[: min(len(word.w), len(self.input_value) + 1)]
        self.hints += 1
        self.show_answer = False
        self.render_panel()

    def next_word(self, message: str) -> None:
        self.index += 1
        self.input_value = ""
        self.hints = 0
        self.show_answer = False
        self.awaiting_next = False
        self.message = message
        self.render_panel()

    def render_panel(self) -> None:
        word = self.current_word
        height = panel_height(self.size.height)
        if word is None:
            self.query_one("#spelling-panel", Static).update(
                text_panel("拼写", ["今日拼写已完成", self.message], "Esc 返回", height)
            )
            return
        masked = f"{self.input_value}{'_' * max(0, len(word.w) - len(self.input_value))}"
        lines = [
            f"进度      {self.index + 1} / {len(self.words)}",
            f"核心释义  {word.core or word.zh or '-'}",
            f"中文释义  {word.zh or '-'}",
            "",
            self.input_line(masked),
        ]
        if self.show_answer:
            lines.append(f"答案      {word.w}")
        lines.append(self.message)
        if self.awaiting_next:
            lines.append("Enter/Space 下一词")
        self.query_one("#spelling-panel", Static).update(
            text_panel("拼写练习", lines, "Enter 提交  Tab 提示  Space 答案", height)
        )

    def action_back(self) -> None:
        self.app.pop_screen()

    def input_line(self, masked: str) -> Text:
        text = Text()
        text.append("> ", style="orange1 bold")
        text.append(masked, style="orange1")
        return text
