"""拼写测试屏幕。"""
from __future__ import annotations

import asyncio
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.widgets import Input, Static

from termi_word.database.models import Word
from termi_word.database.repositories import AppRepository
from termi_word.ui import TermiScreen, rule, make_tui_progress_bar, wrap_display, safe_register_worker, safe_unregister_worker
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
        self.is_busy = False
        self.content_scroll = 0
        self._load_worker = None
        self._submit_worker = None

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            with Horizontal(classes="input-row"):
                yield Static("> ", classes="input-prefix")
                yield Input(id="spelling-input", placeholder="在此键入单词拼写")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.words = []
        self.index = 0
        self.hints = 0
        self.show_answer = False
        self.last_msg = "正在加载拼写词库..."
        self._has_extra_option = False
        self.is_extra = False
        self.submitted = False
        self.content_scroll = 0
        self.is_busy = True

        # 隐藏输入框以防止未就绪时输入
        inp = self.query_one("#spelling-input", Input)
        inp.display = False
        self.query_one(".input-row", Horizontal).display = False

        self.refresh_ui(header="拼写 加载中", lines=["", "  正在加载拼写词库...", ""], message=self.last_msg, footer="Esc 返回")
        self._load_worker = self.run_worker(self._async_load_candidates(), exclusive=True)
        safe_register_worker(self, self._load_worker)

    @property
    def current_word(self) -> Word | None:
        """获取当前测试的单词。"""
        if self.index >= len(self.words):
            return None
        return self.words[self.index]

    def render_word(self) -> None:
        """渲染拼写题目以及状态和提示，支持自适应折行与垂直滚动。"""
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

        # 2. 正常拼写状态显示，计算自适应折行与滚动
        content_height, width = self.compute_dynamic_layout()
        
        bar = make_tui_progress_bar(self.index + 1, len(self.words))
        progress = f"{bar} [{self.index + 1}/{len(self.words)}]"
        
        all_lines = []
        all_lines.extend(wrap_display(f"  [#6B7280]核心释义：[/]{word.core or '-'}", width=width, continuation_indent="            "))
        all_lines.extend(wrap_display(f"  [#6B7280]中文释义：[/]{word.zh or '-'}", width=width, continuation_indent="            "))
        if word.us:
            all_lines.extend(wrap_display(f"  [#6B7280]音标释义：[/]/{word.us}/", width=width, continuation_indent="            "))
        if self.show_answer:
            all_lines.extend(wrap_display(f"  [#F59E0B]正确答案：[/]{word.w}", width=width, continuation_indent="            "))

        # 纵向滚动：截取可见窗口（除去 header+横线 2 行）
        max_visible = max(2, content_height - 2)
        total = len(all_lines)
        if total > max_visible:
            self.content_scroll = max(0, min(self.content_scroll, total - max_visible))
            visible = all_lines[self.content_scroll : self.content_scroll + max_visible]
            indicator = ""
            if self.content_scroll > 0:
                indicator += "↑"
            if self.content_scroll + max_visible < total:
                indicator += "↓"
            if indicator:
                last = visible[-1]
                visible[-1] = last + f" {indicator}"
        else:
            visible = all_lines
        
        mode_label = "额外拼写 输入" if self.is_extra else "拼写 输入"

        # 动态组装页脚与提示并调用统一的基类方法刷新
        if self.submitted:
            self.refresh_ui(
                header=f"{mode_label}  {progress}",
                lines=visible,
                message=self.last_msg or "已完成判定。",
                footer="Enter 下一个单词  Esc 返回"
            )
        else:
            self.refresh_ui(
                header=f"{mode_label}  {progress}",
                lines=visible,
                message=self.last_msg or "",
                footer="Enter 提交判定  Tab 提示  s 跳过  Esc 返回"
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """输入框回车提交。"""
        if event.input.id != "spelling-input":
            return
        
        if self.is_busy:
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
            self.content_scroll = 0
            event.input.value = ""  # 此时确认后才清空输入框内容以作全新状态
            self.render_word()
            return

        typed = event.value.strip()
        if not typed:
            return

        self._do_submit(word, typed)

    def on_key(self, event: Key) -> None:
        """拦截焦点下的特定功能按键。"""
        # 无条件放行全局搜索快捷键，避免被页面内 Key 消费吞掉
        if self.app.is_search_shortcut(event.key):
            event.stop()
            self.app.open_search()
            return

        if self.is_busy:
            event.stop()
            return

        if event.key in ("question_mark", "?"):
            event.stop()
            self.toggle_footer()
            self.render_word()
            return

        # 处于待确认额外学习选项状态下按 Enter
        if self._has_extra_option and event.key == "enter":
            event.stop()
            self._do_load_extra()
            return

        # 处于已判定状态下，按 Enter 键手动切到下一个单词
        if self.submitted and event.key == "enter":
            event.stop()
            self.index += 1
            self.hints = 0
            self.show_answer = False
            self.last_msg = ""
            self.submitted = False
            self.content_scroll = 0
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

        # 任何时候都允许通过上下方向键滚动查看过长的释义
        if key == "up":
            event.stop()
            if self.content_scroll > 0:
                self.content_scroll -= 1
                self.render_word()
            return
        if key == "down":
            event.stop()
            self.content_scroll += 1
            self.render_word()
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
            self.content_scroll = 0
            inp.value = ""
            self.render_word()
            return

    # ── 异步操作 ──────────────────────────────────────────────

    async def _async_load_candidates(self) -> None:
        try:
            words = await asyncio.to_thread(self.app.spelling_service.candidates)
            self.words = words
            self.last_msg = ""
        except Exception as exc:
            self.last_msg = f"加载词库失败: {exc}"
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._load_worker)
            self._load_worker = None
            if getattr(self, "is_mounted", True):
                inp = self.query_one("#spelling-input", Input)
                inp.display = True
                self.query_one(".input-row", Horizontal).display = True
                self.render_word()
                inp.focus()

    def _do_load_extra(self) -> None:
        """加载额外拼写词库。"""
        if self.is_busy:
            return
        self.is_busy = True
        self._has_extra_option = False
        self.last_msg = "正在加载额外词库..."
        self.render_word()

        # 隐藏输入框
        inp = self.query_one("#spelling-input", Input)
        inp.display = False
        self.query_one(".input-row", Horizontal).display = False

        self._load_worker = self.run_worker(self._async_load_extra(), exclusive=True)
        safe_register_worker(self, self._load_worker)

    async def _async_load_extra(self) -> None:
        try:
            words = await asyncio.to_thread(self.app.spelling_service.extra_candidates)
            self.words = words
            self.index = 0
            self.hints = 0
            self.show_answer = False
            self.last_msg = "已进入额外拼写练习模式！"
            self.is_extra = True
            self.submitted = False
        except Exception as exc:
            self.last_msg = f"加载额外词库失败: {exc}"
            self._has_extra_option = True
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._load_worker)
            self._load_worker = None
            if getattr(self, "is_mounted", True):
                inp = self.query_one("#spelling-input", Input)
                inp.display = True
                self.query_one(".input-row", Horizontal).display = True
                self.render_word()
                inp.focus()

    def _do_submit(self, word: Word, typed: str) -> None:
        """异步提交拼写判定。"""
        if self.is_busy:
            return
        self.is_busy = True
        self.last_msg = "正在判定结果并存盘..."
        self.render_word()
        self._submit_worker = self.run_worker(self._async_submit(word, typed), exclusive=True)
        safe_register_worker(self, self._submit_worker)

    async def _async_submit(self, word: Word, typed: str) -> None:
        try:
            result = await asyncio.to_thread(
                self.app.spelling_service.submit, word.id, typed, self.hints
            )
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
            
            # 【优化】判定完不立即清空输入框，方便用户查看对比自己的输入
        except Exception as exc:
            self.last_msg = f"保存判定失败: {exc}"
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._submit_worker)
            self._submit_worker = None
            if getattr(self, "is_mounted", True):
                self.render_word()

    def on_unmount(self) -> None:
        for attr in ("_load_worker", "_submit_worker"):
            worker = getattr(self, attr, None)
            if worker is not None:
                worker.cancel()
                setattr(self, attr, None)
