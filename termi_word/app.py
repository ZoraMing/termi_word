from __future__ import annotations

import asyncio
from time import monotonic

from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Static

from termi_word.config import APP_TITLE, DB_PATH
from termi_word.database import create_session_factory, init_database
from termi_word.screens.calendar import CalendarScreen
from termi_word.screens.review import ReviewScreen
from termi_word.screens.search import SearchScreen
from termi_word.screens.settings import SettingsScreen
from termi_word.screens.spelling import SpellingScreen
from termi_word.screens.today import TodayScreen
from termi_word.screens.word_detail import WordDetailScreen
from termi_word.services.config_service import ConfigService
from termi_word.services.import_service import ImportService
from termi_word.services.search_service import SearchService
from termi_word.services.spelling_service import SpellingService
from termi_word.services.study_service import StudyService


class TermiWordApp(App):
    TITLE = APP_TITLE
    CSS_PATH = "styles/app.tcss"
    ENABLE_COMMAND_PALETTE = False

    def __init__(self) -> None:
        super().__init__()
        self.session_factory = create_session_factory(DB_PATH)
        self.config_service = ConfigService()
        self.import_service = ImportService(self.session_factory)
        self.study_service = StudyService(self.session_factory)
        self.search_service = SearchService(self.session_factory)
        self.spelling_service = SpellingService(self.session_factory)
        self._last_escape_at = 0.0

    def compose(self) -> ComposeResult:
        yield Static("Termi Word 正在启动...", id="boot-status", classes="panel")

    def on_mount(self) -> None:
        self.run_worker(self.bootstrap(), exclusive=True)

    async def bootstrap(self) -> None:
        config = self.config_service.load()
        await asyncio.to_thread(init_database, self.session_factory)
        message = await asyncio.to_thread(self.import_service.ensure_initial_data, config.active_deck)
        boot = self.query_one("#boot-status", Static)
        boot.update(message)
        await asyncio.sleep(0.2)
        boot.remove()
        self.push_screen(TodayScreen())

    def start_study(self, mode: str) -> None:
        self.run_worker(self._start_study(mode), exclusive=True)

    async def _start_study(self, mode: str) -> None:
        config = self.config_service.load()
        cards = await asyncio.to_thread(
            self.study_service.build_queue,
            config.active_deck,
            mode,
            config.daily_new_target,
            config.review_soft_limit,
        )
        self.push_screen(ReviewScreen(cards))

    def open_word_detail(self, word_id: int) -> None:
        self.push_screen(WordDetailScreen(word_id))

    def open_search(self) -> None:
        config = self.config_service.load()
        self.push_screen(SearchScreen(config.active_deck))

    def open_calendar(self) -> None:
        self.push_screen(CalendarScreen())

    def open_settings(self) -> None:
        self.push_screen(SettingsScreen())

    def start_spelling(self) -> None:
        config = self.config_service.load()
        if not config.spelling_enabled:
            self.push_screen(SpellingScreen([], "拼写练习已在设置中关闭"))
            return
        words = self.spelling_service.candidates(config.active_deck, config.daily_spelling_target)
        message = "" if words else "暂无已复习单词可用于拼写"
        self.push_screen(SpellingScreen(words, message))

    def on_key(self, event: Key) -> None:
        if event.key == "ctrl+p":
            event.stop()
            self.open_search()
            return
        if event.key == "ctrl+z":
            event.stop()
            self.exit()
            return
        if event.key != "escape":
            return
        if self.screen.__class__.__name__ != "TodayScreen":
            return
        now = monotonic()
        if now - self._last_escape_at <= 0.8:
            event.stop()
            self.exit()
            return
        self._last_escape_at = now
        event.stop()
