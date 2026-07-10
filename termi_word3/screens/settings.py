"""设置页面屏幕。"""
from __future__ import annotations

from sqlalchemy.exc import StatementError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Static

from termi_word3.database.repositories import AppRepository
from termi_word3.ui import field_row, footer_height, render_content_block, render_footer, rule
from termi_word3.ui.layout import compute_frame_layout


class SettingsScreen(Screen):
    """全局系统配置页面。"""

    can_focus = True

    fields = [
        ("daily_new_target", "每轮新词", "int"),
        ("review_soft_limit", "每轮复习", "int"),
        ("daily_spelling_target", "每日拼写", "int"),
        ("spelling_enabled", "启用拼写", "bool"),
        ("search_shortcut", "搜索快捷键", "text"),
        ("panel_max_width", "最大宽度", "int"),
        ("panel_min_height", "最小高度", "int"),
        ("panel_max_height", "最大高度", "int"),
        ("deck_config", "词书与映射管理", "navigate"),
    ]

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
                elif kind == "text":
                    self.values[key] = str(val or "")
                else:
                    self.values[key] = max(0, int(val or 0))

    def apply_dynamic_layout(self, footer_text: str = "") -> tuple[int, int]:
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

        title = "Settings / Editing" if self.editing else "Settings"
        body_lines = []

        for index, (key, label, kind) in enumerate(self.fields):
            is_sel = index == self.selected
            is_edit = self.editing and is_sel

            if kind == "bool":
                val_str = "是" if self.values[key] else "否"
            elif kind == "text":
                val_str = self.FRIENDLY_SHORTCUTS.get(
                    str(self.values[key]), str(self.values[key])
                )
            else:
                val_str = str(self.values[key])

            body_lines.append(
                field_row(label, val_str, selected=is_sel, editing=is_edit, width=14)
            )

        eff_height = max(1, content_height - 2)
        while len(body_lines) < eff_height:
            body_lines.append("")

        lines = [title, rule(width=width)] + body_lines
        content_widget.update(render_content_block(lines, height=content_height, width=width))
        msg_widget.remove_class("success", "error", "muted")
        if self.last_msg_severity != "info":
            msg_widget.add_class(self.last_msg_severity)

        msg_widget.update(self.last_msg or "按 ↑↓ 选择字段，Enter/Space 修改或切换")
        footer_widget.update(render_footer(footer_text, width))

    def on_key(self, event: Key) -> None:
        """全局键盘事件拦截。"""
        key = event.key
        inp = self.query_one("#settings-input", Input)

        if self.app.is_search_shortcut(key):
            event.stop()
            self.app.open_search()
            return

        if self.editing:
            if key == "escape":
                event.stop()
                self._close_editor()
            return

        # ? 键显示帮助
        if key in ("question_mark", "?"):
            event.stop()
            self.last_msg = "快捷键: ↑↓ 选择字段 | Enter/Space 修改或切换 | Esc 返回"
            self.last_msg_severity = "info"
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

        if key in ("enter", "space"):
            event.stop()
            self._activate_field()
            return

    def _activate_field(self) -> None:
        """激活选中字段。Boolean 直接切换；Int/Text 打开 Input 编辑。"""
        key, label, kind = self.fields[self.selected]
        if kind == "navigate":
            if key == "deck_config":
                from termi_word3.screens.deck_config import DeckConfigScreen
                self.app.push_screen(DeckConfigScreen())
            return
        if kind == "bool":
            self.values[key] = not bool(self.values[key])
            self.last_msg = f"已切换！【{label}】新状态为: {'是' if self.values[key] else '否'}。"
            self.last_msg_severity = "success"
            self._save_values()
            self.render_settings()
            return

        # int/text 类型打开底部输入框
        self.editing = True
        inp_row = self.query_one(".input-row", Horizontal)
        inp = self.query_one("#settings-input", Input)

        self.render_settings()

        inp_row.display = True
        inp.display = True
        if kind == "text":
            friendly = self.FRIENDLY_SHORTCUTS.get(str(self.values[key]), str(self.values[key]))
            inp.value = friendly
            self.last_msg = f"正在修改【{label}】，可选: Ctrl+/ Ctrl+P Ctrl+S Ctrl+F Ctrl+K Ctrl+Q"
        else:
            inp.value = str(self.values[key])
            self.last_msg = f"正在修改【{label}】数值"
        self.last_msg_severity = "info"
        inp.cursor_position = len(inp.value)
        inp.focus()
        self.render_settings()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """提交新的设定值。"""
        if event.input.id != "settings-input":
            return

        key, label, kind = self.fields[self.selected]
        raw = event.value.strip()

        try:
            if kind == "text":
                val = self.SHORTCUT_KEYS.get(raw, raw.lower().replace(" ", ""))
                if not val:
                    raise ValueError("快捷键不能为空")
                self.values[key] = val
                friendly = self.FRIENDLY_SHORTCUTS.get(val, val)
                self._save_values()
                self.last_msg = f"修改成功！【{label}】设定为 {friendly}。"
            else:
                val = int(raw or "0")
                if val < 0:
                    raise ValueError("数值不能为负数")
                
                # 宽高设置边界校验
                if key == "panel_min_height" and not (3 <= val <= 16):
                    raise ValueError("最小高度范围为 3-16")
                if key == "panel_max_height" and not (6 <= val <= 16):
                    raise ValueError("最大高度范围为 6-16")
                if key == "panel_max_width" and val < 20:
                    raise ValueError("最大宽度不能小于 20")

                # 校验最小高度不能大于最大高度
                temp_values = {**self.values, key: val}
                min_h = temp_values.get("panel_min_height", 6)
                max_h = temp_values.get("panel_max_height", 16)
                if min_h > max_h:
                    raise ValueError("最小高度不能大于最大高度")

                self.values[key] = val
                self._save_values()
                self.last_msg = f"修改成功！【{label}】设定为 {val}。"
                self.last_msg_severity = "success"
            self._close_editor()
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

    def _save_values(self) -> None:
        """持久化当前所有的配置修改到 SQLite 数据库中。"""
        try:
            with self.app.session_factory() as session:
                setting = AppRepository(session).get_settings()
                for key, _, kind in self.fields:
                    if kind == "navigate":
                        continue
                    val = self.values[key]
                    if kind == "bool":
                        setattr(setting, key, bool(val))
                    elif kind == "text":
                        setattr(setting, key, str(val or ""))
                    else:
                        setattr(setting, key, max(0, int(val or 0)))
                session.commit()
            # 刷新主应用的搜索快捷键缓存
            self.app.refresh_search_shortcut()
        except Exception as err:
            self.last_msg = f"配置保存失败：{err}"
            self.last_msg_severity = "error"
            self.render_settings()
