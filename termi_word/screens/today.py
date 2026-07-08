from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from termi_word.database.repositories import AppRepository
from termi_word.ui import panel_height, text_panel


class TodayScreen(Screen):
    BINDINGS = [
        ("1", "study", "学习"),
        ("2", "review", "复习"),
        ("4", "spelling", "拼写"),
        ("5", "search", "搜索"),
        ("6", "calendar", "日历"),
        ("7", "settings", "设置"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="today-panel", classes="panel")

    def on_mount(self) -> None:
        self.refresh_summary()

    def on_screen_resume(self) -> None:
        self.refresh_summary()

    def refresh_summary(self) -> None:
        config = self.app.config_service.load()
        with self.app.session_factory() as session:
            stats = AppRepository(session).today_stats(config.active_deck, config.daily_new_target)
        lines = [
            f"词书      {stats.deck_name}",
            f"总词数    {stats.total_words}",
            f"今日词数  {stats.new_done} / {stats.daily_new_target}",
            f"今日复习  {stats.review_done} / {stats.due_reviews}",
            f"剩余新词  {stats.remaining_new}",
            f"剩余天数  {stats.remaining_days}",
            "",
            "1 学习    2 复习    4 拼写",
            "5 搜索    6 日历    7 设置",
        ]
        self.query_one("#today-panel", Static).update(
            text_panel("Termi Word", lines, config.footer["today"], panel_height(self.size.height))
        )

    def action_study(self) -> None:
        self.app.start_study("mixed")

    def action_review(self) -> None:
        self.app.start_study("review")

    def action_search(self) -> None:
        self.app.open_search()

    def action_spelling(self) -> None:
        self.app.start_spelling()

    def action_calendar(self) -> None:
        self.app.open_calendar()

    def action_settings(self) -> None:
        self.app.open_settings()
