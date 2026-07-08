from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static

from termi_word.database.models import Card
from termi_word.services.study_service import ReviewPreview
from termi_word.ui import panel_height, rating_label, scroll_window, text_panel
from rich.text import Text


class ReviewScreen(Screen):
    BINDINGS = [("escape", "back", "返回")]

    def __init__(self, cards: list[Card]) -> None:
        super().__init__()
        self.cards = cards
        self.index = 0
        self.pending_rating: int | None = None
        self.preview: ReviewPreview | None = None
        self.detail_offset = 0
        self.message = ""

    def compose(self) -> ComposeResult:
        yield Static(id="review-panel", classes="panel")

    def on_mount(self) -> None:
        self.render_panel()

    @property
    def current_card(self) -> Card | None:
        if self.index >= len(self.cards):
            return None
        return self.cards[self.index]

    def on_key(self, event: Key) -> None:
        key = event.key
        if key in {"1", "2", "3", "4"}:
            event.stop()
            self.rate(int(key))
            return
        if key in {"enter", "space"}:
            event.stop()
            self.confirm()
            return
        if key == "s":
            event.stop()
            self.next_card("已跳过")
            return
        if key == "up":
            event.stop()
            self.detail_offset = max(0, self.detail_offset - 1)
            self.render_panel()
            return
        if key == "down":
            event.stop()
            self.detail_offset += 1
            self.render_panel()

    def rate(self, rating: int) -> None:
        card = self.current_card
        if card is None:
            return
        self.pending_rating = rating
        self.preview = self.app.study_service.preview(card, rating)
        self.message = f"初评：{rating_label(rating)}，可按 1-4 修正。"
        self.render_panel()

    def confirm(self) -> None:
        card = self.current_card
        if card is None:
            self.app.pop_screen()
            return
        if self.pending_rating is None:
            self.message = "请先按 1-4 初评。"
            self.render_panel()
            return
        feedback = self.app.study_service.commit(card.id, self.pending_rating)
        self.next_card(feedback)

    def next_card(self, message: str) -> None:
        self.index += 1
        self.pending_rating = None
        self.preview = None
        self.detail_offset = 0
        self.message = message
        self.render_panel()

    def render_panel(self) -> None:
        card = self.current_card
        config = self.app.config_service.load()
        height = panel_height(self.size.height)
        if card is None:
            self.query_one("#review-panel", Static).update(
                text_panel("学习", ["今日队列已完成", self.message], "Esc 返回", height)
            )
            return
        word = card.word
        if self.pending_rating is None:
            lines = [
                self.word_heading(word.w, word.us or "", word.c or "-"),
                "",
                "请凭记忆评分，然后查看释义。",
                self.message,
            ]
            footer = config.footer["review_front"]
        else:
            detail_lines = [
                self.word_heading(word.w, word.us or "", word.c or "-"),
                f"核心释义：{word.core}" if word.core else "",
                f"中文释义：{word.zh}" if word.zh else "",
                f"英文定义：{word.en}" if word.en else "",
                f"例句：{word.ex}" if word.ex else "",
                f"翻译：{word.exz}" if word.exz else "",
                "",
                f"评分：{rating_label(self.pending_rating)}  {self.preview.feedback if self.preview else ''}",
                self.message,
            ]
            body_height = max(1, height - 2)
            lines = scroll_window([line for line in detail_lines if line], body_height, self.detail_offset)
            footer = config.footer["review_back"]
        self.query_one("#review-panel", Static).update(
            text_panel(f"学习 {self.index + 1}/{len(self.cards)}", lines, footer, height)
        )

    def word_heading(self, word: str, us: str, category: str) -> Text:
        text = Text()
        text.append(word, style="orange1 bold")
        text.append(f"  {us}  [{category}]")
        return text

    def action_back(self) -> None:
        self.app.pop_screen()
