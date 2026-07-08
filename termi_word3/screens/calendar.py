"""日历打卡与目标配置屏幕。"""
from __future__ import annotations

import calendar
from datetime import date
from sqlalchemy.exc import StatementError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Static

from termi_word3.database.repositories import AppRepository
from termi_word3.ui import rule, render_content_block, field_row


class CalendarScreen(Screen):
    """日历与计划统计配置页。"""

    fields = [
        ("daily_new_target", "每日新词"),
        ("review_soft_limit", "复习上限"),
        ("daily_spelling_target", "每日拼写"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.editing = False
        self.values: dict[str, int] = {}
        self.last_msg = ""

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            with Horizontal(classes="input-row"):
                yield Static("修改为 > ", classes="input-prefix")
                yield Input(id="calendar-input", placeholder="输入新目标数字...")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.query_one("#calendar-input", Input).display = False
        self.query_one(".input-row", Horizontal).display = False
        self.load_values()
        self.render_calendar()

    def load_values(self) -> None:
        """从 SQLite 加载各个目标字段的当前配置值。"""
        with self.app.session_factory() as session:
            setting = AppRepository(session).get_settings()
            self.values = {
                "daily_new_target": max(0, int(setting.daily_new_target or 0)),
                "review_soft_limit": max(0, int(setting.review_soft_limit or 0)),
                "daily_spelling_target": max(0, int(setting.daily_spelling_target or 0)),
            }

    def render_calendar(self) -> None:
        """渲染核心 7 行日历与目标配置行。"""
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)

        with self.app.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            reviewed = repo.today_review_count()
            spelled = repo.today_spelling_count()
            streak = repo.streak_days()

        today = date.today()
        # 得到本月日历行 (取前两周展示)
        weeks = calendar.monthcalendar(today.year, today.month)
        month_rows = []
        for week in weeks[:2]:
            row_str = " ".join(" ." if day == 0 else f"{day:2d}" for day in week)
            month_rows.append(row_str)

        lines = [
            f"Calendar & Goals  {today.year}-{today.month:02d}",
            f"  Mon Tue Wed Thu Fri Sat Sun   {month_rows[0]} | {month_rows[1] if len(month_rows)>1 else ''}",
            f"  实际进度：复习 {reviewed:<3} 拼写 {spelled:<3}  连续打卡 {streak:<2} 天",
            rule(),
        ]

        # 渲染 3 个可编辑的目标字段
        for index, (key, label) in enumerate(self.fields):
            is_sel = index == self.selected
            is_edit = self.editing and is_sel
            val = self.values[key]
            lines.append(
                field_row(label, val, selected=is_sel, editing=is_edit, width=14)
            )

        content_widget.update(render_content_block(lines, height=7))
        msg_widget.update(self.last_msg or "按 ↑↓ 选择字段，按 Enter 键修改目标值")
        footer_widget.update(self.app.ui_config.footer("calendar"))

    def on_key(self, event: Key) -> None:
        """全局键盘逻辑拦截。"""
        key = event.key
        inp = self.query_one("#calendar-input", Input)

        if self.editing:
            # 编辑中如果按 Esc 则退出编辑状态
            if key == "escape":
                event.stop()
                self._close_editor()
            return

        if key == "escape":
            event.stop()
            self.app.pop_screen()
            return

        if key == "up":
            event.stop()
            self.selected = max(0, self.selected - 1)
            self.last_msg = ""
            self.render_calendar()
            return

        if key == "down":
            event.stop()
            self.selected = min(len(self.fields) - 1, self.selected + 1)
            self.last_msg = ""
            self.render_calendar()
            return

        if key in ("enter", "space"):
            event.stop()
            self._open_editor()
            return

    def _open_editor(self) -> None:
        """激活底部 Input 进行数值输入。"""
        key, label = self.fields[self.selected]
        self.editing = True
        
        inp_row = self.query_one(".input-row", Horizontal)
        inp = self.query_one("#calendar-input", Input)
        
        inp_row.display = True
        inp.display = True
        inp.value = str(self.values[key])
        inp.cursor_position = len(inp.value)
        inp.focus()
        
        self.last_msg = f"正在修改【{label}】数值"
        self.render_calendar()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """数字输入提交。"""
        if event.input.id != "calendar-input":
            return
        
        key, label = self.fields[self.selected]
        try:
            val = int(event.value.strip() or "0")
            if val < 0:
                raise ValueError("数值不能小于 0")
            
            # 更新本地及数据库
            self.values[key] = val
            self._save_values()
            self.last_msg = f"已保存修改！【{label}】新目标为 {val}。"
            self._close_editor()
        except (ValueError, StatementError) as err:
            self.last_msg = f"输入错误：{err}"
            self.render_calendar()

    def _close_editor(self) -> None:
        """关闭并隐藏输入框。"""
        self.editing = False
        inp_row = self.query_one(".input-row", Horizontal)
        inp = self.query_one("#calendar-input", Input)
        inp.display = False
        inp_row.display = False
        self.focus()
        self.render_calendar()

    def _save_values(self) -> None:
        """同步并持久化配置更改到数据库。"""
        with self.app.session_factory() as session:
            setting = AppRepository(session).get_settings()
            setting.daily_new_target = max(0, int(self.values["daily_new_target"]))
            setting.review_soft_limit = max(0, int(self.values["review_soft_limit"]))
            setting.daily_spelling_target = max(0, int(self.values["daily_spelling_target"]))
            session.commit()
