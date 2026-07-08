from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static
from rich.text import Text

from termi_word.ui import panel_height, text_panel


class SettingsScreen(Screen):
    BINDINGS = [("escape", "back", "返回")]

    fields = [
        ("active_deck", "当前词包", "str"),
        ("daily_new_target", "每日新词", "int"),
        ("review_soft_limit", "复习上限", "int"),
        ("daily_spelling_target", "每日拼写", "int"),
        ("spelling_enabled", "启用拼写", "bool"),
        ("import_start_row", "导入起始行", "int"),
        ("import_end_row", "导入结束行", "int"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.editing = False
        self.values: dict[str, int | bool | str] = {}
        self.edit_buffer = ""
        self.message = ""

    def compose(self) -> ComposeResult:
        yield Static(id="settings-panel", classes="panel")

    def on_mount(self) -> None:
        self.load_values()
        self.render_panel()

    def load_values(self) -> None:
        config = self.app.config_service.load()
        self.values = {
            "active_deck": config.active_deck,
            "daily_new_target": config.daily_new_target,
            "review_soft_limit": config.review_soft_limit,
            "daily_spelling_target": config.daily_spelling_target,
            "spelling_enabled": config.spelling_enabled,
            "import_start_row": config.import_start_row,
            "import_end_row": config.import_end_row,
        }

    def render_panel(self) -> None:
        lines = []
        for index, (key, label, kind) in enumerate(self.fields):
            prefix = ">_" if self.editing and index == self.selected else ("> " if index == self.selected else "  ")
            value = self.edit_buffer if self.editing and index == self.selected else self.format_value(self.values[key], kind)
            line = f"{prefix}{label:<10} {value}"
            lines.append(self.accent_line(line) if index == self.selected else line)
        lines.extend(["", self.message])
        self.query_one("#settings-panel", Static).update(
            text_panel("设置", lines, "↑↓ 选择  Enter 编辑/切换  Esc 返回", panel_height(self.size.height))
        )

    def on_key(self, event: Key) -> None:
        if self.editing:
            if event.key in {"ctrl+z", "ctrl+p"}:
                return
            event.stop()
            if event.key == "enter":
                self.submit_editor()
            elif event.key == "backspace":
                self.edit_buffer = self.edit_buffer[:-1]
                self.render_panel()
            elif len(event.character or "") == 1:
                # 获取当前字段的类型
                _, _, kind = self.fields[self.selected]
                # 对 int 类型只允许数字
                if kind == "int" and not event.character.isdigit():
                    return
                # 对 str 类型只允许字母、数字、下划线、中横线作为词包名称
                if kind == "str" and not (event.character.isalnum() or event.character in {"_", "-"}):
                    return
                self.edit_buffer += event.character
                self.render_panel()
            return
        if event.key == "up":
            event.stop()
            self.selected = max(0, self.selected - 1)
            self.render_panel()
        elif event.key == "down":
            event.stop()
            self.selected = min(len(self.fields) - 1, self.selected + 1)
            self.render_panel()
        elif event.key in {"enter", "space"}:
            event.stop()
            self.activate_field()

    def activate_field(self) -> None:
        key, label, kind = self.fields[self.selected]
        if kind == "bool":
            self.values[key] = not bool(self.values[key])
            self.save_values(f"{label} 已保存")
            return
        self.editing = True
        self.edit_buffer = str(self.values[key])
        self.message = f"正在编辑：{label}"
        self.render_panel()

    def submit_editor(self) -> None:
        key, label, kind = self.fields[self.selected]
        try:
            self.values[key] = self.parse_value(self.edit_buffer, kind)
        except ValueError as error:
            self.message = f"保存失败：{error}"
            self.render_panel()
            return
        self.close_editor()
        self.save_values(f"{label} 已保存")

    def close_editor(self) -> None:
        self.editing = False
        self.edit_buffer = ""

    def save_values(self, message: str) -> None:
        self.app.config_service.save_values(self.values)
        self.message = message
        self.render_panel()

    def parse_value(self, raw: str, kind: str) -> int | bool | str:
        if kind == "str":
            val = raw.strip()
            if not val:
                raise ValueError("不能为空")
            return val
        if kind == "bool":
            return raw.strip().lower() in {"1", "true", "yes", "on", "是"}
        value = int(raw.strip() or "0")
        if value < 0:
            raise ValueError("不能小于 0")
        return value

    def format_value(self, value: int | bool | str, kind: str) -> str:
        if kind == "str":
            return str(value)
        return "是" if kind == "bool" and value else ("否" if kind == "bool" else str(value))

    def accent_line(self, value: str) -> Text:
        text = Text()
        text.append(value, style="orange1")
        return text

    def action_back(self) -> None:
        if self.editing:
            self.close_editor()
            self.message = "已取消编辑"
            self.render_panel()
            return
        self.app.pop_screen()
