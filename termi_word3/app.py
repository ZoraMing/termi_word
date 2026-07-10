"""Termi Word 主应用入口。"""
from __future__ import annotations

import asyncio
from time import monotonic

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.widgets import Static

from termi_word3.config import APP_TITLE, DEFAULT_DB_PATH
from termi_word3.database.engine import create_session_factory, init_database
from termi_word3.screens.calendar import CalendarScreen

from termi_word3.screens.review import ReviewScreen
from termi_word3.screens.settings import SettingsScreen
from termi_word3.screens.spelling import SpellingScreen
from termi_word3.screens.today import TodayScreen
from termi_word3.screens.word_detail import WordDetailScreen
from termi_word3.screens.words import WordsScreen
from termi_word3.services.import_service import ImportService
from termi_word3.services.spelling_service import SpellingService
from termi_word3.services.study_service import StudyService
from termi_word3.services.ui_config_service import UiConfigService


class TermiWordApp(App):
    """Termi Word 3 主应用。"""

    TITLE = APP_TITLE
    CSS_PATH = "styles/app.tcss"

    # 全局绑定：priority=True 使该绑定优先于子 Widget（含 Input 的焦点处理）
    # 这样即使 Input 有焦点，Ctrl+/ 也能被 App 捕获并触发 action_open_search
    BINDINGS = [
        Binding("ctrl+slash", "open_search", "全局搜索", priority=True, show=False),
        Binding("ctrl+underscore", "open_search", "全局搜索", priority=True, show=False),
        Binding("ctrl+_", "open_search", "全局搜索", priority=True, show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session_factory = create_session_factory(DEFAULT_DB_PATH)
        self.import_service = ImportService(self.session_factory)
        self.study_service = StudyService(self.session_factory)
        self.spelling_service = SpellingService(self.session_factory)
        self.ui_config = UiConfigService()
        self._last_escape_at = 0.0
        self._search_shortcut = "ctrl+slash"

    def compose(self) -> ComposeResult:
        yield Static("Termi Word 正在启动...", id="boot-status")

    def on_mount(self) -> None:
        self.run_worker(self.bootstrap(), exclusive=True)

    async def bootstrap(self) -> None:
        """异步执行数据库初始化、默认数据载入，并安装所有屏。"""
        await asyncio.to_thread(init_database, self.session_factory)
        await asyncio.to_thread(self.import_service.ensure_initial_data)

        # 加载搜索快捷键配置
        from termi_word3.database.repositories import AppRepository
        with self.session_factory() as session:
            setting = AppRepository(session).get_settings()
            self._search_shortcut = getattr(setting, "search_shortcut", None) or "ctrl+slash"

        self.query_one("#boot-status", Static).remove()

        # 安装页面屏
        self.install_screen(TodayScreen(), name="today")
        self.install_screen(SpellingScreen(), name="spelling")
        self.install_screen(WordsScreen(), name="words")
        self.install_screen(CalendarScreen(), name="calendar")
        self.install_screen(SettingsScreen(), name="settings")
        self.push_screen("today")

    def start_study(self, mode: str) -> None:
        """生成学习计划队列并跳转至背词学习屏。"""
        self.run_worker(self._start_study(mode), exclusive=True)

    async def _start_study(self, mode: str) -> None:
        queue = await asyncio.to_thread(self.study_service.build_today_queue, mode)
        # 跳转至学习背词页，将卡片队列及会话 ID 传入
        self.push_screen(ReviewScreen(queue.cards, queue.session_id, is_extra=queue.is_extra))

    def action_open_search(self, deck_id: int | None = None) -> None:
        """全局搜索动作（由 BINDINGS 触发，priority=True 绕过 Input 焦点拦截）。
        若当前栈顶已是词表页，则清空并重新聚焦搜索框，而非重复 push。
        """
        # 如果词表页已在栈顶，直接复用（清空搜索 + 聚焦输入框）
        if self.screen.__class__.__name__ == "WordsScreen":
            try:
                from textual.widgets import Input
                inp = self.screen.query_one("#words-search-input", Input)
                inp.value = ""
                inp.focus()
                self.screen.call_later(self.screen.render_words)
            except Exception:
                pass
            return
        self.push_screen(WordsScreen(focus_search=True, deck_id=deck_id))


    def open_search(self, deck_id: int | None = None) -> None:
        """全局直达词表搜索并直接聚焦输入框（向后兼容调用方式）。"""
        self.action_open_search(deck_id)

    def open_word_detail(self, word_id: int) -> None:
        """打开单词详情页"""
        self.push_screen(WordDetailScreen(word_id))

    def go_back(self) -> None:
        """pop 返回上一屏，如果已是首页则不操作。"""
        if self.screen.__class__.__name__ != "TodayScreen":
            self.pop_screen()

    def refresh_search_shortcut(self) -> None:
        """从数据库重新加载搜索快捷键配置（设置页修改后调用）。"""
        from termi_word3.database.repositories import AppRepository
        with self.session_factory() as session:
            setting = AppRepository(session).get_settings()
            self._search_shortcut = getattr(setting, "search_shortcut", None) or "ctrl+slash"

    def is_search_shortcut(self, key: str) -> bool:
        """统一判断全局搜索快捷键，兼容历史默认键值。"""
        return key in {
            self._search_shortcut,
            "ctrl+slash",
            "ctrl+/",
            "ctrl+_",
            "ctrl+underscore",
            "ctrl+shift+slash",
            "ctrl+shift+underscore",
        }

    def on_key(self, event: Key) -> None:
        """全局键盘事件拦截分发。
        - ctrl+c / ctrl+z: 直接退出程序。
        - 搜索快捷键（兼容后备，BINDINGS 处理不到的键名变体）。
        - escape:
          - 双击 (0.8s内) 退出程序；
          - 若非首页，pop 返回上一屏。
        """
        key = event.key
        if key in ("ctrl+z",):
            event.stop()
            self.exit()
            return

        # 后备层：BINDINGS 未映射到的其他键名变体（不同终端编码差异）
        if self.is_search_shortcut(key):
            event.stop()
            self.action_open_search()
            return

        if key == "escape":
            now = monotonic()
            # 双击 Esc (时间间隔 <= 0.8s) 退出应用
            if now - self._last_escape_at <= 0.8:
                event.stop()
                self.exit()
                return
            self._last_escape_at = now

            if self.screen.__class__.__name__ != "TodayScreen":
                event.stop()
                self.go_back()
