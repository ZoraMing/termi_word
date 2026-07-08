"""拼写测试屏幕。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Static

from termi_word3.database.models import Word
from termi_word3.ui import rule, render_content_block


class SpellingScreen(Screen):
    """拼写评测练习页面，包含输入判定、字母提示及答案展示。"""

    def __init__(self) -> None:
        super().__init__()
        self.words: list[Word] = []
        self.index = 0
        self.hints = 0
        self.show_answer = False
        self.last_msg = ""

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            with Horizontal(classes="input-row"):
                yield Static("> ", classes="input-prefix")
                yield Input(id="spelling-input", placeholder="在此键入单词拼写")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.words = self.app.spelling_service.candidates()
        self.index = 0
        self.hints = 0
        self.show_answer = False
        self.last_msg = ""
        self.render_word()
        self.query_one("#spelling-input", Input).focus()

    @property
    def current_word(self) -> Word | None:
        """获取当前测试的单词。"""
        if self.index >= len(self.words):
            return None
        return self.words[self.index]

    def render_word(self) -> None:
        """渲染核心 6 行拼写题目以及状态和提示。"""
        word = self.current_word
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)
        inp = self.query_one("#spelling-input", Input)

        # 1. 完成状态
        if word is None:
            lines = [
                "Spelling Practice / Complete",
                rule(),
                "",
                "      今日拼写练习任务已全部完成！",
                "",
                "      请按 Esc 键返回主界面。",
            ]
            content_widget.update(render_content_block(lines, height=6))
            msg_widget.update("")
            footer_widget.update("Esc 返回首页")
            inp.display = False
            self.query_one(".input-row", Horizontal).display = False
            return

        # 2. 正常拼写状态显示
        progress = f"[{self.index + 1}/{len(self.words)}]"
        answer_line = f"  正确答案：{word.w}" if self.show_answer else ""
        us_str = f"音标释义：/{word.us}/" if word.us else ""
        
        lines = [
            f"Spelling Practice  {progress}",
            rule(),
            f"  核心释义：{word.core or '-'}",
            f"  中文释义：{word.zh or '-'}",
            f"  {us_str}" if us_str else "",
            answer_line,
        ]

        content_widget.update(render_content_block(lines, height=6))
        msg_widget.update(self.last_msg or "按字母键输入，按 Enter 键提交判定")
        footer_widget.update(self.app.ui_config.footer("spelling"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """输入框回车提交。"""
        if event.input.id != "spelling-input":
            return
        
        word = self.current_word
        if word is None:
            return

        typed = event.value.strip()
        if not typed:
            return

        # 判定拼写结果
        ok = self.app.spelling_service.submit(word.id, typed, self.hints)
        if ok:
            self.last_msg = "太棒了，拼写正确！"
        else:
            self.last_msg = f"拼写错误。正确拼写应为: {word.w}"

        # 切入下一词
        self.index += 1
        self.hints = 0
        self.show_answer = False
        event.input.value = ""  # 清空输入
        self.render_word()

    def on_key(self, event: Key) -> None:
        """拦截焦点下的特定功能按键。"""
        word = self.current_word
        if word is None:
            if event.key == "escape":
                event.stop()
                self.app.pop_screen()
            return

        key = event.key
        inp = self.query_one("#spelling-input", Input)

        if key == "escape":
            event.stop()
            self.app.pop_screen()
            return

        # Tab 提示下一个字母
        if key == "tab":
            event.stop()
            next_len = min(len(word.w), len(inp.value) + 1)
            inp.value = word.w[:next_len]
            inp.cursor_position = len(inp.value)
            self.hints += 1
            self.show_answer = False
            self.render_word()
            return

        # 空白时按 Space 看答案
        if key == "space" and not inp.value:
            event.stop()
            self.show_answer = True
            self.render_word()
            return

        # 空白时按 s 跳过
        if key == "s" and not inp.value:
            event.stop()
            self.index += 1
            self.hints = 0
            self.show_answer = False
            self.last_msg = "已跳过该单词。"
            self.render_word()
            return
