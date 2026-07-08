"""设置页面屏幕。"""
from __future__ import annotations

from sqlalchemy.exc import StatementError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Static

from termi_word3.database.repositories import AppRepository
from termi_word3.ui import render_content_block, field_row


class SettingsScreen(Screen):
    """全局系统配置页面。"""

    fields = [
        ("daily_new_target", "每日新词", "int"),
        ("review_soft_limit", "复习上限", "int"),
        ("daily_spelling_target", "每日拼写", "int"),
        ("spelling_enabled", "启用拼写", "bool"),
        ("show_us", "显示音标", "bool"),
        ("show_en", "显示英文", "bool"),
        ("show_examples", "显示例句", "bool"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.editing = False
        self.values: dict[str, int | bool] = {}
        self.deck_name = "无活跃词本"
        self.last_msg = ""

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            with Horizontal(classes="input-row"):
                yield Static("设置值为 > ", classes="input-prefix")
                yield Input(id="settings-input", placeholder="输入新的设置值...")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.query_one("#settings-input", Input).display = False
        self.query_one(".input-row", Horizontal).display = False
        self._load_values()
        self.render_settings()

    def _load_values(self) -> None:
        """从 SQLite 获取当前的全部配置记录。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            deck = repo.active_deck()
            self.deck_name = deck.name if deck else "无词本"

            self.values = {}
            for key, _, kind in self.fields:
                val = getattr(setting, key)
                if kind == "bool":
                    self.values[key] = bool(val)
                else:
                    self.values[key] = max(0, int(val or 0))

    def render_settings(self) -> None:
        """渲染设置项，自适应高度调整以保证总高为 12 行。"""
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)

        # 自适应高度控制：
        # 如果是编辑态，我们需要展示输入框，所以核心字符区高度限为 7 行（只展示 7 个设置字段）；
        # 如果是非编辑态，输入框隐藏，高度为 8 行（包括 1 行 Settings 词本头部 + 7 个设置字段）。
        h = 7 if self.editing else 8
        lines = []

        if not self.editing:
            lines.append(f"Settings  [当前词本: {self.deck_name}]")

        for index, (key, label, kind) in enumerate(self.fields):
            is_sel = index == self.selected
            is_edit = self.editing and is_sel
            
            # 格式化 Boolean
            if kind == "bool":
                val_str = "是" if self.values[key] else "否"
            else:
                val_str = str(self.values[key])

            lines.append(
                field_row(label, val_str, selected=is_sel, editing=is_edit, width=14)
            )

        content_widget.update(render_content_block(lines, height=h))
        msg_widget.update(self.last_msg or "按 ↑↓ 选择字段，Enter/Space 修改或切换")
        footer_widget.update(self.app.ui_config.footer("settings"))

    def on_key(self, event: Key) -> None:
        """全局键盘事件拦截。"""
        key = event.key
        inp = self.query_one("#settings-input", Input)

        if self.editing:
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
        """激活选中字段。Boolean 键直接切换；Int 键打开 Input 键盘。"""
        key, label, kind = self.fields[self.selected]
        if kind == "bool":
            self.values[key] = not bool(self.values[key])
            self.last_msg = f"已切换！【{label}】新状态为: {'是' if self.values[key] else '否'}。"
            self._save_values()
            self.render_settings()
            return

        # int 类型打开底部输入框
        self.editing = True
        inp_row = self.query_one(".input-row", Horizontal)
        inp = self.query_one("#settings-input", Input)
        
        # 激活前先刷新高度，把 content-area 调整为 7 行以给输入行腾出空间
        self.render_settings()
        
        inp_row.display = True
        inp.display = True
        inp.value = str(self.values[key])
        inp.cursor_position = len(inp.value)
        inp.focus()
        
        self.last_msg = f"正在修改【{label}】数值"
        self.render_settings()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """提交新的数值型设定。"""
        if event.input.id != "settings-input":
            return
        
        key, label, kind = self.fields[self.selected]
        try:
            val = int(event.value.strip() or "0")
            if val < 0:
                raise ValueError("数值不能为负数")
            
            self.values[key] = val
            self._save_values()
            self.last_msg = f"修改成功！【{label}】设定为 {val}。"
            self._close_editor()
        except (ValueError, StatementError) as err:
            self.last_msg = f"输入错误：{err}"
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
                    val = self.values[key]
                    if kind == "bool":
                        setattr(setting, key, bool(val))
                    else:
                        setattr(setting, key, max(0, int(val or 0)))
                session.commit()
        except Exception as err:
            self.last_msg = f"配置保存失败：{err}"
            self.render_settings()
