"""设置页面屏幕。"""
from __future__ import annotations

import asyncio
from sqlalchemy.exc import StatementError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Static

from termi_word.config import (
    DEFAULT_PANEL_MIN_HEIGHT,
    DEFAULT_PANEL_MAX_HEIGHT,
    PANEL_MIN_HEIGHT_RANGE,
    PANEL_MAX_HEIGHT_RANGE,
    PANEL_MAX_WIDTH_RANGE,
)
from termi_word.database.repositories import AppRepository
from termi_word.services.home_shortcut_service import (
    HOME_ACTIONS,
    normalize_shortcut,
    validate_home_shortcuts,
)
from termi_word.services.time_service import TimeSettingsService, format_offset, parse_offset
from termi_word.ui import (
    field_row,
    is_footer_visible,
    render_content_block,
    render_footer,
    rule,
    scroll_window,
    toggle_footer_visible,
    safe_register_worker,
    safe_unregister_worker,
)
from termi_word.ui.layout import compute_frame_layout


class SettingsScreen(Screen):
    """全局系统配置页面。"""

    can_focus = True
    PLAN_FIELDS = {"daily_new_target", "review_soft_limit", "daily_spelling_target"}

    fields = [
        ("daily_new_target", "每轮新词", "int"),
        ("review_soft_limit", "每轮复习", "int"),
        ("daily_spelling_target", "每日拼写", "int"),
        ("search_shortcut", "搜索快捷键", "text"),
        ("home_key_study", "快捷键: 学习", "home_key"),
        ("home_key_review", "快捷键: 复习", "home_key"),
        ("home_key_spelling", "快捷键: 拼写", "home_key"),
        ("home_key_words", "快捷键: 词表", "home_key"),
        ("home_key_calendar", "快捷键: 日历", "home_key"),
        ("home_key_settings", "快捷键: 设置", "home_key"),
        ("timezone_offset_minutes", "本地时区", "timezone"),
        ("panel_max_width", "最大宽度", "int"),
        ("panel_min_height", "最小高度", "int"),
        ("panel_max_height", "最大高度", "int"),
        ("deck_config", "词书与映射管理", "navigate"),
    ]
    sections = {
        0: "学习计划",
        3: "快捷键",
        10: "时间与界面",
        14: "词书管理",
    }

    # 快捷键友好名称映射
    FRIENDLY_SHORTCUTS = {
        "ctrl+slash": "Ctrl+/",
        "ctrl+p": "Ctrl+P",
        "ctrl+s": "Ctrl+S",
        "ctrl+f": "Ctrl+F",
        "ctrl+k": "Ctrl+K",
        "ctrl+q": "Ctrl+Q",
    }
    SHORTCUT_KEYS = {v: k for k, v in FRIENDLY_SHORTCUTS.items()}

    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.editing = False
        self.values: dict[str, int | bool | str] = {}
        self.deck_name = "无活跃词本"
        self.last_msg = ""
        self.last_msg_severity = "info"
        self._settings_scroll_offset = 0
        self.is_busy = False
        self._save_worker = None

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            with Horizontal(classes="input-row"):
                yield Static("> ", classes="input-prefix")
                yield Input(id="settings-input", placeholder="输入新的设置值...")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.query_one("#settings-input", Input).display = False
        self.query_one(".input-row", Horizontal).display = False
        self._load_values()
        self.render_settings()
        self.focus()

    def _load_values(self) -> None:
        """从 SQLite 获取当前的全部配置记录。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            deck = repo.active_deck()
            self.deck_name = deck.name if deck else "无词本"

            self.values = {}
            for key, _, kind in self.fields:
                if kind == "navigate":
                    self.values[key] = ">>"
                    continue
                val = getattr(setting, key)
                if kind == "bool":
                    self.values[key] = bool(val)
                elif kind == "timezone":
                    self.values[key] = int(val) if val is not None else 0
                elif kind in {"text", "home_key"}:
                    self.values[key] = str(val or "")
                else:
                    self.values[key] = max(0, int(val or 0))

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
        self.render_settings()

    def render_settings(self) -> None:
        """渲染设置项，根据数据库宽高自适应渲染。"""
        footer_text = self.app.ui_config.footer("settings")
        content_height, width = self.apply_dynamic_layout(footer_text)
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)

        title = "设置 编辑" if self.editing else "设置"
        body_lines = []
        selected_line = 0

        for index, (key, label, kind) in enumerate(self.fields):
            if index in self.sections:
                body_lines.append(f"[muted]{self.sections[index]}[/]")
            is_sel = index == self.selected
            is_edit = self.editing and is_sel
            if is_sel:
                selected_line = len(body_lines)

            if kind == "bool":
                val_str = "是" if self.values[key] else "否"
            elif kind == "timezone":
                val_str = format_offset(int(self.values[key]))
            elif kind in {"text", "home_key"}:
                val_str = self.FRIENDLY_SHORTCUTS.get(
                    str(self.values[key]), str(self.values[key])
                )
            else:
                val_str = str(self.values[key])

            body_lines.append(
                field_row(label, val_str, selected=is_sel, editing=is_edit, width=14)
            )

        eff_height = max(1, content_height - 2)
        self._settings_scroll_offset = self._clamp_scroll(selected_line, eff_height)
        visible_body = scroll_window(body_lines, eff_height, self._settings_scroll_offset)

        lines = [title, rule(width=width)] + visible_body
        content_widget.update(render_content_block(lines, height=content_height, width=width))
        msg_widget.remove_class("success", "error", "muted")
        if self.last_msg_severity != "info":
            msg_widget.add_class(self.last_msg_severity)

        msg_widget.update(self.last_msg or "↑↓ 选择字段   Space 选中/切换   Enter 确认")
        footer_output = render_footer(footer_text, width) if is_footer_visible(self) else ""
        footer_widget.update(footer_output)

    def _clamp_scroll(self, selected_line: int, height: int) -> int:
        """让当前选中项始终留在可视区域内。"""
        total_lines = len(self.fields) + len(self.sections)
        max_offset = max(0, total_lines - height)
        offset = max(0, min(self._settings_scroll_offset, max_offset))
        if selected_line < offset:
            return selected_line
        if selected_line >= offset + height:
            return min(max_offset, selected_line - height + 1)
        return offset

    def on_key(self, event: Key) -> None:
        """全局键盘事件拦截。"""
        key = event.key
        inp = self.query_one("#settings-input", Input)

        if self.app.is_search_shortcut(key):
            event.stop()
            self.app.open_search()
            return

        if self.is_busy:
            event.stop()
            return

        if self.editing:
            if key == "escape":
                event.stop()
                self._close_editor()
            return

        if key in ("question_mark", "?"):
            event.stop()
            toggle_footer_visible(self)
            self.render_settings()
            return

        if key == "escape":
            event.stop()
            self.app.pop_screen()
            return

        if key == "up":
            event.stop()
            self.selected = max(0, self.selected - 1)
            self.last_msg = ""
            self.render_settings()
            return

        if key == "down":
            event.stop()
            self.selected = min(len(self.fields) - 1, self.selected + 1)
            self.last_msg = ""
            self.render_settings()
            return

        if key == "space":
            event.stop()
            self._activate_field()
            return

        if key == "enter":
            event.stop()
            self._activate_field()
            return

    def _activate_field(self) -> None:
        """激活选中字段。Boolean 直接切换；Int/Text 打开 Input 编辑。"""
        key, label, kind = self.fields[self.selected]
        if kind == "navigate":
            if key == "deck_config":
                from termi_word.screens.deck_config import DeckConfigScreen
                self.app.push_screen(DeckConfigScreen())
            return
        if kind == "bool":
            self.values[key] = not bool(self.values[key])
            self._do_save_settings()
            return

        # int/text 类型打开底部输入框
        self.editing = True
        inp_row = self.query_one(".input-row", Horizontal)
        inp = self.query_one("#settings-input", Input)

        self.render_settings()

        inp_row.display = True
        inp.display = True
        if kind == "timezone":
            inp.value = format_offset(int(self.values[key]))
            self.last_msg = f"正在修改【{label}】，示例: +08:00，按 Enter 确认"
        elif kind == "home_key":
            inp.value = str(self.values[key])
            self.last_msg = f"正在修改【{label}】，按 Enter 确认"
        elif kind == "text":
            friendly = self.FRIENDLY_SHORTCUTS.get(str(self.values[key]), str(self.values[key]))
            inp.value = friendly
            self.last_msg = f"正在修改【{label}】，可选: Ctrl+/ Ctrl+P 等，按 Enter 确认"
        else:
            inp.value = str(self.values[key])
            self.last_msg = f"正在修改【{label}】数值，按 Enter 确认"
        self.last_msg_severity = "info"
        inp.cursor_position = len(inp.value)
        inp.focus()
        self.render_settings()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """提交新的设定值。"""
        if event.input.id != "settings-input":
            return

        if self.is_busy:
            return

        key, label, kind = self.fields[self.selected]
        raw = event.value.strip()

        try:
            if kind == "timezone":
                val = parse_offset(raw)
                self.values[key] = val
                self._do_save_settings()
            elif kind == "home_key":
                val = normalize_shortcut(raw)
                self.values[key] = val
                self._do_save_settings()
            elif kind == "text":
                val = self.SHORTCUT_KEYS.get(raw, raw.lower().replace(" ", ""))
                if not val:
                    raise ValueError("快捷键不能为空")
                self.values[key] = val
                self._do_save_settings()
            else:
                val = int(raw or "0")
                if val < 0:
                    raise ValueError("数值不能为负数")

                # 宽高设置边界校验（统一使用 config.py 常量）
                if key == "panel_min_height" and not (PANEL_MIN_HEIGHT_RANGE[0] <= val <= PANEL_MIN_HEIGHT_RANGE[1]):
                    raise ValueError(f"最小高度范围为 {PANEL_MIN_HEIGHT_RANGE[0]}-{PANEL_MIN_HEIGHT_RANGE[1]}")
                if key == "panel_max_height" and not (PANEL_MAX_HEIGHT_RANGE[0] <= val <= PANEL_MAX_HEIGHT_RANGE[1]):
                    raise ValueError(f"最大高度范围为 {PANEL_MAX_HEIGHT_RANGE[0]}-{PANEL_MAX_HEIGHT_RANGE[1]}")
                if key == "panel_max_width" and not (PANEL_MAX_WIDTH_RANGE[0] <= val <= PANEL_MAX_WIDTH_RANGE[1]):
                    raise ValueError(f"最大宽度范围为 {PANEL_MAX_WIDTH_RANGE[0]}-{PANEL_MAX_WIDTH_RANGE[1]}")

                # 校验最小高度不能大于最大高度
                temp_values = {**self.values, key: val}
                min_h = temp_values.get("panel_min_height", DEFAULT_PANEL_MIN_HEIGHT)
                max_h = temp_values.get("panel_max_height", DEFAULT_PANEL_MAX_HEIGHT)
                if min_h > max_h:
                    raise ValueError("最小高度不能大于最大高度")

                self.values[key] = val
                self._do_save_settings(reset_study_sessions=key in self.PLAN_FIELDS)
        except (ValueError, StatementError) as err:
            self.last_msg = f"输入错误：{err}"
            self.last_msg_severity = "error"
            self.render_settings()

    def _close_editor(self) -> None:
        """隐藏输入控件，并将 content-area 恢复成 8 行。"""
        self.editing = False
        inp_row = self.query_one(".input-row", Horizontal)
        inp = self.query_one("#settings-input", Input)
        inp.display = False
        inp_row.display = False
        self.focus()
        self.render_settings()

    def _do_save_settings(self, reset_study_sessions: bool = False) -> None:
        """异步保存设置。"""
        self.is_busy = True
        self.last_msg = "正在保存配置..."
        self.last_msg_severity = "info"
        self.render_settings()
        self._save_worker = self.run_worker(
            self._async_save_settings(reset_study_sessions), exclusive=True
        )
        safe_register_worker(self, self._save_worker)

    async def _async_save_settings(self, reset_study_sessions: bool = False) -> None:
        try:
            await asyncio.to_thread(self._save_values_db, reset_study_sessions)
            key, label, kind = self.fields[self.selected]
            if kind == "bool":
                self.last_msg = f"已切换！【{label}】新状态为: {'是' if self.values[key] else '否'}。"
            else:
                friendly = self.FRIENDLY_SHORTCUTS.get(str(self.values[key]), str(self.values[key]))
                self.last_msg = f"修改成功。【{label}】设定为 {friendly}。"
            self.last_msg_severity = "success"

            if getattr(self, "is_mounted", True):
                self._close_editor()
        except Exception as exc:
            self.last_msg = f"保存设置失败: {exc}"
            self.last_msg_severity = "error"
            try:
                await asyncio.to_thread(self._load_values)
            except Exception:
                pass
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._save_worker)
            self._save_worker = None
            if getattr(self, "is_mounted", True):
                self.render_settings()

    def _save_values_db(self, reset_study_sessions: bool = False) -> None:
        """持久化当前所有的配置修改到 SQLite 数据库中（在后台线程中运行）。"""
        shortcuts = {
            action: normalize_shortcut(self.values[f"home_key_{action}"])
            for action, _label in HOME_ACTIONS
        }
        reserved = {
            normalize_shortcut(self.values.get("search_shortcut")),
            "ctrl+/",
            "ctrl+_",
            "ctrl+underscore",
            "ctrl+shift+slash",
            "ctrl+shift+underscore",
        }
        validate_home_shortcuts(shortcuts, reserved=reserved)

        with self.app.session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            for key, _, kind in self.fields:
                if kind == "navigate":
                    continue
                val = self.values[key]
                if kind == "bool":
                    setattr(setting, key, bool(val))
                elif kind == "timezone":
                    setattr(setting, key, int(val) if val is not None else None)
                elif kind in {"text", "home_key"}:
                    setattr(setting, key, str(val or ""))
                else:
                    setattr(setting, key, max(0, int(val or 0)))
            if reset_study_sessions:
                deck = repo.active_deck()
                if deck is not None:
                    repo.close_open_sessions(deck.id)
            session.commit()

        self.app.refresh_settings_cache()
        # 保存时区配置到数据库
        timezone_val = self.values.get("timezone_offset_minutes")
        if timezone_val is not None:
            TimeSettingsService(self.app.session_factory).save_config(int(timezone_val))

    def on_unmount(self) -> None:
        if self._save_worker is not None:
            self._save_worker.cancel()
            self._save_worker = None
