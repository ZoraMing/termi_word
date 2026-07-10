"""拼写测试屏幕。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.widgets import Input, Static

from termi_word.database.models import Word
from termi_word.database.repositories import AppRepository
from termi_word.ui import TermiScreen, rule, make_tui_progress_bar
from termi_word.ui.messages import format_spelling_result


class SpellingScreen(TermiScreen):
    """拼写评测练习页面，包含输入判定、字母提示及答案展示。"""

    def __init__(self) -> None:
        super().__init__()
        self.words: list[Word] = []
        self.index = 0
        self.hints = 0
        self.show_answer = False
        self.last_msg = ""
        self._has_extra_option = False
        self.is_extra = False
        self.submitted = False

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
        self._has_extra_option = False
        self.is_extra = False
        self.submitted = False
        self.render_word()
        self.query_one("#spelling-input", Input).focus()

    @property
    def current_word(self) -> Word | None:
        """获取当前测试的单词。"""
        if self.index >= len(self.words):
            return None
        return self.words[self.index]

    def render_word(self) -> None:
        """渲染拼写题目以及状态和提示。"""
        word = self.current_word
        inp = self.query_one("#spelling-input", Input)

        # 1. 完成状态
        if word is None:
            extra_words = self.app.spelling_service.extra_candidates()
            inp.display = False
            self.query_one(".input-row", Horizontal).display = False
            
            if extra_words:
                lines = [
                    "",
                    "      今日拼写练习目标已完成。",
                    "",
                    "      还有可用词汇，您可以继续练习。",
                    "      按 Enter 键加载 20 个额外拼写单词，",
                    "      或按 Esc 返回。",
                ]
                self._has_extra_option = True
                self.refresh_ui(
                    header="拼写 继续",
                    lines=lines,
                    message="",
                    footer="Enter 额外拼写  Esc 返回"
                )
            else:
                lines = [
                    "",
                    "      今日拼写练习任务已完成。",
                    "",
                    "      按 Esc 返回。",
                ]
                self._has_extra_option = False
                self.refresh_ui(
                    header="拼写 完成",
                    lines=lines,
                    message="",
                    footer="Esc 返回"
                )
            return

        # 2. 正常拼写状态显示
        bar = make_tui_progress_bar(self.index + 1, len(self.words))
        progress = f"{bar} [{self.index + 1}/{len(self.words)}]"
        answer_line = f"  正确答案：{word.w}" if self.show_answer else ""
        us_str = f"音标释义：/{word.us}/" if word.us else ""
        
        mode_label = "额外拼写 输入" if self.is_extra else "拼写 输入"
        lines = [
            f"  核心释义：{word.core or '-'}",
            f"  中文释义：{word.zh or '-'}",
            f"  {us_str}" if us_str else "",
            answer_line,
        ]

        # 动态组装页脚与提示并调用统一的基类方法刷新
        if self.submitted:
            self.refresh_ui(
                header=f"{mode_label}  {progress}",
                lines=lines,
                message=self.last_msg or "已完成判定。",
                footer="Enter 下一个单词  Esc 返回"
            )
        else:
            self.refresh_ui(
                header=f"{mode_label}  {progress}",
                lines=lines,
                message=self.last_msg or "请在输入框内键入单词拼写",
                footer="Enter 提交判定  Tab 提示  Space 答案  s 跳过  Esc 返回"
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """输入框回车提交。"""
        if event.input.id != "spelling-input":
            return
        
        word = self.current_word
        if word is None:
            return

        # 如果已经判定过了，第二次回车代表手动切入下一个单词
        if self.submitted:
            self.index += 1
            self.hints = 0
            self.show_answer = False
            self.last_msg = ""
            self.submitted = False
            event.input.value = ""  # 清空输入框内容以作全新状态
            self.render_word()
            return

        typed = event.value.strip()
        if not typed:
            return

        # 判定拼写结果 (第一次回车)
        result = self.app.spelling_service.submit(word.id, typed, self.hints)
        if result:
            self.submitted = True
            if result.is_correct:
                self.last_msg = f"拼写正确！按 Enter 键继续..."
            else:
                self.show_answer = True
                self.last_msg = f"拼写错误！正确答案是: {word.w}，按 Enter 键继续..."
        else:
            self.last_msg = "单词不存在"
            self.submitted = True

        event.input.value = ""  # 判定完立刻清空输入框
        self.render_word()

    def on_key(self, event: Key) -> None:
        """拦截焦点下的特定功能按键。"""
        # 无条件放行全局搜索快捷键，避免被页面内 Key 消费吞掉
        if self.app.is_search_shortcut(event.key):
            event.stop()
            self.app.open_search()
            return

        if event.key in ("question_mark", "?"):
            event.stop()
            self.toggle_footer()
            self.render_word()
            return

        # 处于待确认额外学习选项状态下按 Enter
        if self._has_extra_option and event.key == "enter":
            event.stop()
            self._has_extra_option = False
            self.words = self.app.spelling_service.extra_candidates()
            self.index = 0
            self.hints = 0
            self.show_answer = False
            self.last_msg = "已进入额外拼写练习模式！"
            self.is_extra = True
            self.submitted = False
            
            # 显示输入框并聚焦
            inp = self.query_one("#spelling-input", Input)
            inp.value = ""
            inp.display = True
            self.query_one(".input-row", Horizontal).display = True
            
            self.render_word()
            inp.focus()
            return

        # 处于已判定状态下，按 Enter 键手动切到下一个单词
        if self.submitted and event.key == "enter":
            event.stop()
            self.index += 1
            self.hints = 0
            self.show_answer = False
            self.last_msg = ""
            self.submitted = False
            self.query_one("#spelling-input", Input).value = ""
            self.render_word()
            return

        word = self.current_word
        if word is None:
            if event.key == "escape":
                event.stop()
                self.app.pop_screen()
            elif event.key == "enter":
                event.stop()
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
