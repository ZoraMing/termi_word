"""Termi Word 主应用入口。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from time import monotonic

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.widgets import Static

from termi_word.config import APP_TITLE, DEFAULT_DB_PATH
from termi_word.database.engine import create_session_factory, init_database
from termi_word.runtime_paths import RUNTIME_PATHS, ensure_data_directories
from termi_word.screens.calendar import CalendarScreen

from termi_word.screens.review import ReviewScreen
from termi_word.screens.settings import SettingsScreen
from termi_word.screens.spelling import SpellingScreen
from termi_word.screens.today import TodayScreen
from termi_word.screens.word_detail import WordDetailScreen
from termi_word.screens.words import WordsScreen
from termi_word.services.import_service import ImportService
from termi_word.services.spelling_service import SpellingService
from termi_word.services.study_service import StudyService
from termi_word.services.time_service import TimeSettingsService
from termi_word.services.ui_config_service import UiConfigService


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
        ensure_data_directories(RUNTIME_PATHS)
        self._engine = None  # 显式存储引擎引用，便于生命周期管理
        self.session_factory = create_session_factory(DEFAULT_DB_PATH)
        # 保存引擎引用
        self._engine = self.session_factory.kw.get("bind")
        self.import_service = ImportService(self.session_factory)
        self.study_service = StudyService(self.session_factory)
        self.spelling_service = SpellingService(self.session_factory)
        self.ui_config = UiConfigService(self.session_factory)
        self.time_settings = TimeSettingsService(self.session_factory)
        self.settings = SimpleNamespace(
            search_shortcut="ctrl+slash",
            panel_max_width=120,
            panel_min_height=6,
            panel_max_height=16,
            timezone_offset_minutes=None,
            home_key_study="1",
            home_key_review="2",
            home_key_spelling="3",
            home_key_words="4",
            home_key_calendar="5",
            home_key_settings="6",
        )
        self._last_escape_at = 0.0
        self._search_shortcut = "ctrl+slash"
        self._bootstrap_worker = None
        self._study_worker = None
        self._managed_workers = []
        self._is_exiting = False

    def compose(self) -> ComposeResult:
        yield Static("Termi Word 正在启动...", id="boot-status")

    def on_mount(self) -> None:
        self._bootstrap_worker = self.run_worker(self.bootstrap(), exclusive=True)

    async def bootstrap(self) -> None:
        """异步执行数据库初始化、默认数据载入，并安装所有屏。"""
        await asyncio.to_thread(init_database, self.session_factory)
        await asyncio.to_thread(self._migrate_old_configs)
        await asyncio.to_thread(self._ensure_local_time_settings)
        await asyncio.to_thread(self.import_service.ensure_initial_data)
        await asyncio.to_thread(self.refresh_settings_cache)

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
        self._study_worker = self.run_worker(self._start_study(mode), exclusive=True)

    async def _start_study(self, mode: str) -> None:
        queue = await asyncio.to_thread(self.study_service.build_today_queue, mode)
        # 跳转至学习背词页，将卡片队列及会话 ID 传入
        self.push_screen(ReviewScreen(queue.cards, queue.session_id, is_extra=queue.is_extra, mode=mode))

    def action_open_search(self, deck_id: int | None = None) -> None:
        """全局搜索动作（由 BINDINGS 触发，priority=True 绕过 Input 焦点拦截）。
        若当前栈顶已是词表页，则保留查询并重新聚焦搜索框，而非重复 push。
        """
        # 如果词表页已在栈顶，直接复用（保留查询 + 聚焦输入框）
        if self.screen.__class__.__name__ == "WordsScreen":
            try:
                self.screen.focus_search_input()
            except Exception as exc:
                self.log.warning(f"无法聚焦词表搜索: {exc}")
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

    def register_worker(self, worker) -> None:
        """登记需要在应用退出时统一取消的后台 worker。"""
        if worker is not None and worker not in self._managed_workers:
            self._managed_workers.append(worker)

    def unregister_worker(self, worker) -> None:
        """移除已结束或已取消的后台 worker。"""
        if worker is not None and worker in self._managed_workers:
            self._managed_workers.remove(worker)

    def request_exit(self) -> None:
        """集中处理应用退出前的后台任务取消与数据库连接释放。"""
        if getattr(self, "_is_exiting", False):
            return
        self._is_exiting = True

        workers = [
            getattr(self, "_bootstrap_worker", None),
            getattr(self, "_study_worker", None),
            *list(getattr(self, "_managed_workers", [])),
        ]
        for worker in workers:
            if worker is not None:
                worker.cancel()
        if hasattr(self, "_managed_workers"):
            self._managed_workers.clear()

        # 使用显式存储的引擎引用，避免依赖 SQLAlchemy 内部实现
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

        self.exit()

    def refresh_search_shortcut(self) -> None:
        """从数据库重新加载搜索快捷键配置（设置页修改后调用）。"""
        self.refresh_settings_cache()
        self._search_shortcut = getattr(self.settings, "search_shortcut", None) or "ctrl+slash"

    def refresh_settings_cache(self) -> None:
        """刷新渲染路径使用的设置缓存，避免高频 UI 重绘同步读库。"""
        from termi_word.database.repositories import AppRepository
        with self.session_factory() as session:
            setting = AppRepository(session).get_settings()
            self.settings = SimpleNamespace(
                search_shortcut=getattr(setting, "search_shortcut", None) or "ctrl+slash",
                panel_max_width=int(getattr(setting, "panel_max_width", 120) or 120),
                panel_min_height=int(getattr(setting, "panel_min_height", 6) or 6),
                panel_max_height=int(getattr(setting, "panel_max_height", 16) or 16),
                timezone_offset_minutes=getattr(setting, "timezone_offset_minutes", None),
                home_key_study=getattr(setting, "home_key_study", None) or "1",
                home_key_review=getattr(setting, "home_key_review", None) or "2",
                home_key_spelling=getattr(setting, "home_key_spelling", None) or "3",
                home_key_words=getattr(setting, "home_key_words", None) or "4",
                home_key_calendar=getattr(setting, "home_key_calendar", None) or "5",
                home_key_settings=getattr(setting, "home_key_settings", None) or "6",
                daily_new_target=getattr(setting, "daily_new_target", 20),
                review_soft_limit=getattr(setting, "review_soft_limit", 100),
                daily_spelling_target=getattr(setting, "daily_spelling_target", 15),
                show_us=getattr(setting, "show_us", True),
                show_en=getattr(setting, "show_en", True),
                show_examples=getattr(setting, "show_examples", True),
            )
            self._search_shortcut = self.settings.search_shortcut

    def _migrate_old_configs(self) -> None:
        """迁移旧版本的配置文件到数据库。"""
        from termi_word.runtime_paths import migrate_old_configs_to_db
        migrate_old_configs_to_db(RUNTIME_PATHS.data_dir, self.session_factory)

    def _ensure_local_time_settings(self) -> None:
        """启动时校验一次系统时区，并把结果写入数据库。"""
        self.time_settings.ensure_config()

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
        - ctrl+q / ctrl+z: 直接退出程序。
        - 搜索快捷键（兼容后备，BINDINGS 处理不到的键名变体）。
        - escape:
          - 双击 (0.8s内) 退出程序；
          - 若非首页，pop 返回上一屏。
        """
        key = event.key
        if key in ("ctrl+q", "ctrl+z"):
            event.stop()
            self.request_exit()
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
                self.request_exit()
                return
            self._last_escape_at = now

            if self.screen.__class__.__name__ != "TodayScreen":
                event.stop()
                self.go_back()


def main() -> None:
    """Termi Word 统一启动入口。"""
    app = TermiWordApp()
    app.run()


if __name__ == "__main__":
    main()

