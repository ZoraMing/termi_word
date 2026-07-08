"""Termi Word 主应用入口。"""
from __future__ import annotations

import asyncio
from time import monotonic

from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Static

from termi_word3.config import APP_TITLE, DEFAULT_DB_PATH
from termi_word3.database.engine import create_session_factory, init_database
from termi_word3.screens.calendar import CalendarScreen
from termi_word3.screens.review import ReviewScreen
from termi_word3.screens.settings import SettingsScreen
from termi_word3.screens.spelling import SpellingScreen
from termi_word3.screens.today import TodayScreen
from termi_word3.screens.words import WordsScreen
from termi_word3.services.import_service import ImportService
from termi_word3.services.spelling_service import SpellingService
from termi_word3.services.study_service import StudyService
from termi_word3.services.ui_config_service import UiConfigService


class TermiWordApp(App):
    """Termi Word 3 主应用。"""

    TITLE = APP_TITLE
    CSS_PATH = "styles/app.tcss"

    def __init__(self) -> None:
        super().__init__()
        self.session_factory = create_session_factory(DEFAULT_DB_PATH)
        self.import_service = ImportService(self.session_factory)
        self.study_service = StudyService(self.session_factory)
        self.spelling_service = SpellingService(self.session_factory)
        self.ui_config = UiConfigService()
        self._last_escape_at = 0.0

    def compose(self) -> ComposeResult:
        yield Static("Termi Word 正在启动...", id="boot-status")

    def on_mount(self) -> None:
        self.run_worker(self.bootstrap(), exclusive=True)

    async def bootstrap(self) -> None:
        """异步执行数据库初始化、默认数据载入，并安装所有屏。"""
        await asyncio.to_thread(init_database, self.session_factory)
        await asyncio.to_thread(self.import_service.ensure_initial_data)

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
        self.push_screen(ReviewScreen(queue.cards, queue.session_id))

    def open_search(self) -> None:
        """全局直达词表搜索并直接聚焦输入框。"""
        self.push_screen(WordsScreen(focus_search=True))

    def go_back(self) -> None:
        """pop 返回上一屏，如果已是首页则不操作。"""
        if self.screen.__class__.__name__ != "TodayScreen":
            self.pop_screen()

    def on_key(self, event: Key) -> None:
        """全局键盘事件拦截分发。
        - ctrl+c / ctrl+z: 直接退出程序。
        - ctrl+/ (ctrl+slash): 进入词表并聚焦搜索。
        - escape:
          - 双击 (0.8s内) 退出程序；
          - 若非首页，pop 返回上一屏。
        """
        key = event.key
        if key in ("ctrl+c", "ctrl+z"):
            event.stop()
            self.exit()
            return

        if key in ("ctrl+slash", "ctrl+/"):
            event.stop()
            self.open_search()
            return

        if key == "escape":
            now = monotonic()
            # 双击 Esc (时间间隔 <= 0.8s) 退出应用
            if now - self._last_escape_at <= 0.8:
                event.stop()
                self.exit()
                return
            self._last_escape_at = now

            # 如果当前屏幕中存在被聚焦的 Input（正处于输入状态），由 Screen 自身的按键处理去释放焦点；
            # 否则，返回上一页面
            if self.screen.__class__.__name__ != "TodayScreen":
                # 只有在非输入态下才触发 pop_screen
                # 我们让 event 传导给当前的 Screen 先判定是否拦截，因此这里暂不直接 go_back，
                # 具体的 go_back 我们在每个 Screen 收到 escape 时自行处理或在这里统一但避开输入框聚焦。
                # 我们可以让 Screen 的 on_key 优先处理，所以全局 escape 处理我们留给各个 screen 确认；
                # 但如果不是输入态，我们在 Screen 内部自行 pop。为了健壮性，这里仅对 Today 以外的逃生泡泡起作用：
                pass
