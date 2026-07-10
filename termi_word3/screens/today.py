"""首页 - 今日概览与功能导航页。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static

from termi_word3.database.repositories import AppRepository
from termi_word3.services.home_shortcut_service import (
    format_home_help,
    format_home_menu,
    home_shortcuts_from_setting,
)
from termi_word3.ui import render_content_block, render_footer, rule
from termi_word3.ui.layout import compute_frame_layout


class TodayScreen(Screen):
    """今日背词概览与大厅导航页面。"""

    BINDINGS = [
        ("1", "study", "继续学习"),
        ("2", "review_only", "仅复习"),
        ("3", "spelling", "拼写练习"),
        ("4", "words", "词表"),
        ("5", "calendar", "打卡日历"),
        ("6", "settings", "设置参数"),
    ]

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.refresh_summary()

    def on_screen_resume(self) -> None:
        self.refresh_summary()

    def on_key(self, event: Key) -> None:
        """全局键盘逻辑拦截。"""
        if self.app.is_search_shortcut(event.key):
            event.stop()
            self.app.open_search()
            return

        shortcuts = home_shortcuts_from_setting(getattr(self.app, "settings", None))
        actions = {
            shortcuts["study"]: self.action_study,
            shortcuts["review"]: self.action_review_only,
            shortcuts["spelling"]: self.action_spelling,
            shortcuts["words"]: self.action_words,
            shortcuts["calendar"]: self.action_calendar,
            shortcuts["settings"]: self.action_settings,
        }
        action = actions.get(event.key)
        if action is not None:
            event.stop()
            action()
            return

        if event.key in ("question_mark", "?"):
            event.stop()
            msg_widget = self.query_one("#message-area", Static)
            msg_widget.remove_class("success", "error")
            msg_widget.add_class("muted")
            msg_widget.update(format_home_help(shortcuts))
            return

    def apply_dynamic_layout(self, footer_text: str = "") -> tuple[int, int]:
        setting = getattr(self.app, "settings", None)
        if setting is None:
            with self.app.session_factory() as session:
                setting = AppRepository(session).get_settings()
        
        layout = compute_frame_layout(
            terminal_width=self.size.width,
            terminal_height=self.size.height,
            panel_min_height=setting.panel_min_height,
            panel_max_height=setting.panel_max_height,
            panel_max_width=setting.panel_max_width,
            footer_text=footer_text,
            has_input=False,
            message_rows=1,
        )
        
        container = self.query_one(".frame-container", Static)
        container.styles.height = layout.frame_height
        container.styles.min_height = layout.frame_height
        container.styles.max_height = layout.frame_height
        container.styles.width = layout.frame_width
        
        self.query_one("#footer-area", Static).styles.height = layout.footer_rows

        content = self.query_one("#content-area", Static)
        content.styles.height = layout.content_height
        content.styles.min_height = layout.content_height
        content.styles.max_height = layout.content_height
        
        return layout.content_height, layout.content_width

    def on_resize(self) -> None:
        """窗口缩放事件，重新刷新渲染页面。"""
        self.refresh_summary()

    def refresh_summary(self) -> None:
        """从 SQLite 加载数据，重新刷新核心内容区。"""
        setting = getattr(self.app, "settings", None)
        cached_shortcuts = home_shortcuts_from_setting(setting)
        footer_text = f"{format_home_help(cached_shortcuts)}   Ctrl+/ 搜索"
        content_height, width = self.apply_dynamic_layout(footer_text)

        with self.app.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            if setting is None:
                setting = repo.get_settings()
            shortcuts = home_shortcuts_from_setting(setting)
            
            deck_id = deck.id if deck else None
            deck_name = deck.name if deck else "无词本"
            total = repo.word_count(deck_id) if deck else 0
            
            # 今日进度
            new_done, rev_done = repo.today_new_and_review_counts()
            spelled = repo.today_spelling_count()
            streak = repo.streak_days()
            
            # 剩余新词数
            remaining = repo.remaining_new_count(deck.id) if deck else 0

        # 精确格式化核心静态字符画，自适应宽度
        title_fill = " " * max(1, width - len("Termi Word") - len("v1.0") - 2)
        lines = [
            f"Termi Word{title_fill}v1.0",
            rule(width=width),
            f"当前词本：{deck_name:<10}  总词数：{total:<6}",
            f"每轮配置：新词 {setting.daily_new_target:<3} 复习 {setting.review_soft_limit:<3}   今日计划：拼写 {setting.daily_spelling_target:<3}",
            f"当前完成：新词 [#F59E0B]{new_done:<2}[/]  复习 [#00D4AA]{rev_done:<3}[/]  拼写 [#00D4AA]{spelled:<3}[/]  连续打卡 [#4ADE80]{streak:<2}[/] 天",
            f"坚持计划：剩余新词数 {remaining:<5}",
            rule(width=width),
            format_home_menu(shortcuts),
        ]

        self.query_one("#content-area", Static).update(
            render_content_block(lines, height=content_height, width=width)
        )
        
        msg_widget = self.query_one("#message-area", Static)
        msg_widget.remove_class("success", "error", "muted")
        if total == 0:
            msg_widget.add_class("error")
            msg_widget.update(f"词本为空。请在 [{shortcuts['settings']}] 设置中同步词包。")
        else:
            msg_widget.update("")
            
        footer = f"{format_home_help(shortcuts)}   Ctrl+/ 搜索"
        self.query_one("#footer-area", Static).update(render_footer(footer, width))

    # 快捷键动作分发
    def action_study(self) -> None:
        self.app.start_study("mixed")

    def action_review_only(self) -> None:
        self.app.start_study("review")

    def action_spelling(self) -> None:
        self.app.push_screen("spelling")

    def action_words(self) -> None:
        self.app.push_screen("words")

    def action_calendar(self) -> None:
        self.app.push_screen("calendar")

    def action_settings(self) -> None:
        self.app.push_screen("settings")
