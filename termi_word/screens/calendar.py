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

from termi_word.database.repositories import AppRepository
from termi_word.ui import (
    field_row,
    is_footer_visible,
    render_content_block,
    render_footer,
    rule,
    toggle_footer_visible,
)
from termi_word.ui.layout import compute_frame_layout


class CalendarScreen(Screen):
    """日历与计划统计配置页。"""

    can_focus = True

    fields = [
        ("daily_new_target", "每轮新词"),
        ("review_soft_limit", "每轮复习"),
        ("daily_spelling_target", "每日拼写"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.editing = False
        self.values: dict[str, int] = {}
        self.last_msg = ""
        self.last_msg_severity = "info"

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            with Horizontal(classes="input-row"):
                yield Static("> ", classes="input-prefix")
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
            has_input=self.editing,
            message_rows=1,
            footer_visible=is_footer_visible(self),
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
        self.render_calendar()

    def render_calendar(self) -> None:
        """渲染完整月历与目标配置行。"""
        footer_text = self.app.ui_config.footer("calendar")
        content_height, width = self.apply_dynamic_layout(footer_text)
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)

        today = date.today()
        month_last_day = calendar.monthrange(today.year, today.month)[1]
        month_start = date(today.year, today.month, 1)
        month_end = date(today.year, today.month, month_last_day)

        with self.app.session_factory() as session:
            repo = AppRepository(session)
            reviewed = repo.today_review_count()
            spelled = repo.today_spelling_count()
            streak = repo.streak_days()
            active_dates = repo.activity_dates_between(month_start, month_end)

        weeks = calendar.monthcalendar(today.year, today.month)

        month_rows = []
        for week in weeks:
            cells = []
            for day in week:
                if day == 0:
                    cells.append(" .")
                else:
                    cur_date = date(today.year, today.month, day)
                    day_str = f"{day:2d}"
                    if day == today.day:
                        day_str = f">{day:1d}"
                    
                    if cur_date in active_dates:
                        # 绿色高亮完成目标打卡的日期
                        cells.append(f"[bold #4ADE80]{day_str}[/]")
                    else:
                        cells.append(day_str)
            month_rows.append(" ".join(cells))

        if self.editing:
            # 编辑模式: 标题 + 裁剪后的日历 + 字段配置行
            lines = [f"日历 编辑  {today.year}-{today.month:02d}"]
            calendar_limit = max(1, content_height - len(self.fields) - 1)
            lines.extend(month_rows[:calendar_limit])
            lines.extend(self._plan_field_lines(editing=True))
            content_widget.update(render_content_block(lines, height=content_height, width=width))
        else:
            # 正常模式: 标题 + weekday + 裁剪后的日历 + 统计与目标值展示
            lines = [
                f"日历 浏览  {today.year}-{today.month:02d}",
                "  Mo Tu We Th Fr Sa Su",
            ]
            calendar_limit = max(1, content_height - len(self.fields) - 4)
            lines.extend(month_rows[:calendar_limit])
            lines.append(
                f"  今日打卡: 复习 {reviewed}  拼写 {spelled}  连续 {streak} 天"
            )
            lines.extend(self._plan_field_lines(editing=False))
            content_widget.update(render_content_block(lines, height=content_height, width=width))

        msg_widget.remove_class("success", "error", "muted")
        if self.last_msg_severity != "info":
            msg_widget.add_class(self.last_msg_severity)
        else:
            msg_widget.add_class("muted")

        msg_widget.update(self.last_msg or "按 ↑↓ 选择字段，Enter 键修改")
        footer_output = render_footer(footer_text, width) if is_footer_visible(self) else ""
        footer_widget.update(footer_output)

    def on_key(self, event: Key) -> None:
        """全局键盘逻辑拦截。"""
        # 无条件放行全局搜索快捷键，避免被页面内 Key 消费吞掉
        if self.app.is_search_shortcut(event.key):
            event.stop()
            self.app.open_search()
            return

        key = event.key
        inp = self.query_one("#calendar-input", Input)

        if self.editing:
            # 编辑中如果按 Esc 则退出编辑状态
            if key == "escape":
                event.stop()
                self._close_editor()
            return

        if key in ("question_mark", "?"):
            event.stop()
            toggle_footer_visible(self)
            self.render_calendar()
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
        self.last_msg_severity = "info"
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
            self.last_msg_severity = "success"
            self._close_editor()
        except (ValueError, StatementError) as err:
            self.last_msg = f"输入错误：{err}"
            self.last_msg_severity = "error"
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
            repo = AppRepository(session)
            setting = repo.get_settings()
            setting.daily_new_target = max(0, int(self.values["daily_new_target"]))
            setting.review_soft_limit = max(0, int(self.values["review_soft_limit"]))
            setting.daily_spelling_target = max(0, int(self.values["daily_spelling_target"]))
            deck = repo.active_deck()
            if deck is not None:
                repo.close_open_sessions(deck.id)
            session.commit()

    def _plan_field_lines(self, editing: bool) -> list[str]:
        """返回每日学习计划字段行，保证光标选择始终可见。"""
        lines = []
        for index, (key, label) in enumerate(self.fields):
            is_sel = index == self.selected
            lines.append(
                field_row(
                    label,
                    self.values[key],
                    selected=is_sel,
                    editing=editing and is_sel,
                    width=14,
                )
            )
        return lines
