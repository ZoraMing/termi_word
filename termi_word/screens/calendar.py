from __future__ import annotations

from datetime import date

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static
from rich.text import Text

from termi_word.database.repositories import AppRepository
from termi_word.ui import panel_height, text_panel


class CalendarScreen(Screen):
    BINDINGS = [("escape", "back", "返回")]

    def __init__(self) -> None:
        super().__init__()
        self.day_offset = 0

    def compose(self) -> ComposeResult:
        yield Static(id="calendar-panel", classes="panel")

    def on_mount(self) -> None:
        self.render_panel()

    def render_panel(self) -> None:
        config = self.app.config_service.load()
        with self.app.session_factory() as session:
            stats = AppRepository(session).calendar_stats(config.active_deck, config.daily_new_target)
        if stats.days:
            self.day_offset = max(0, min(self.day_offset, len(stats.days) - 1))
        lines = [
            f"连续学习  {stats.streak_days} 天",
            f"今日完成  新词 {stats.today_new}  复习 {stats.today_review}",
            f"剩余新词  {stats.remaining_new}  预计 {stats.remaining_days} 天",
            "",
        ]
        for item in stats.days[self.day_offset :]:
            line = f"  {item.day:%m-%d}  到期 {item.due_reviews:<3} 已复习 {item.reviewed:<3}"
            if item.day == date.today():
                today_line = Text()
                today_line.append(f"> {item.day:%m-%d}  到期 {item.due_reviews:<3} 已复习 {item.reviewed:<3}", style="orange1 bold")
                lines.append(today_line)
            else:
                lines.append(line)
        self.query_one("#calendar-panel", Static).update(
            text_panel("日历 / 复习计划", lines, config.footer.get("calendar", "Esc 返回"), panel_height(self.size.height))
        )

    def on_key(self, event: Key) -> None:
        if event.key == "up":
            event.stop()
            self.day_offset = max(0, self.day_offset - 1)
            self.render_panel()
        elif event.key == "down":
            event.stop()
            self.day_offset = self.day_offset + 1
            self.render_panel()

    def action_back(self) -> None:
        self.app.pop_screen()
