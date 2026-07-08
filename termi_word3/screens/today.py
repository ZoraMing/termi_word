"""首页 - 今日概览与功能导航页。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from termi_word3.database.repositories import AppRepository
from termi_word3.ui import rule, render_content_block


class TodayScreen(Screen):
    """今日背词概览与大厅导航页面。"""

    BINDINGS = [
        ("1", "study", "继续学习"),
        ("2", "review_only", "仅复习"),
        ("3", "new_only", "仅新词"),
        ("4", "spelling", "拼写练习"),
        ("5", "words", "词词表"),
        ("6", "calendar", "打卡日历"),
        ("7", "settings", "设置参数"),
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

    def refresh_summary(self) -> None:
        """从 SQLite 加载数据，重新刷新 8 行核心内容区。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            setting = repo.get_settings()
            
            deck_id = deck.id if deck else None
            deck_name = deck.name if deck else "无词本"
            total = repo.word_count(deck_id) if deck else 0
            
            # 今日进度
            new_done, rev_done = repo.today_new_and_review_counts()
            spelled = repo.today_spelling_count()
            streak = repo.streak_days()
            
            # 剩余新词数
            remaining = repo.remaining_new_count(deck.id) if deck else 0

        # 精确格式化 8 行核心静态字符画 (宽 68 字符)
        lines = [
            f"Termi Word                                            v1.0",
            rule(),
            f"当前词本：{deck_name:<10}  总词数：{total:<6}",
            f"今日计划：新词 {setting.daily_new_target:<3} 复习 {setting.review_soft_limit:<3} 拼写 {setting.daily_spelling_target:<3}",
            f"当前完成：新词 {new_done:<2}  复习 {rev_done:<3}  拼写 {spelled:<3}  连续打卡 {streak:<2} 天",
            f"坚持计划：剩余新词数 {remaining:<5}",
            rule(),
            f"[1]继续学习  [2]复习  [3]新词  [4]拼写  [5]词表  [6]日历  [7]设置",
        ]

        self.query_one("#content-area", Static).update(
            render_content_block(lines, height=8)
        )
        self.query_one("#message-area", Static).update("")
        self.query_one("#footer-area", Static).update(
            self.app.ui_config.footer("today")
        )

    # 快捷键动作分发
    def action_study(self) -> None:
        self.app.start_study("mixed")

    def action_review_only(self) -> None:
        self.app.start_study("review")

    def action_new_only(self) -> None:
        self.app.start_study("new")

    def action_spelling(self) -> None:
        self.app.push_screen("spelling")

    def action_words(self) -> None:
        self.app.push_screen("words")

    def action_calendar(self) -> None:
        self.app.push_screen("calendar")

    def action_settings(self) -> None:
        self.app.push_screen("settings")
