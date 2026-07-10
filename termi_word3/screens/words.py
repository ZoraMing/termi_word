"""词表展示与搜索屏幕。"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Static
from rich.markup import escape

from termi_word3.database.models import Word
from termi_word3.database.repositories import AppRepository
from termi_word3.ui import footer_height, render_content_block, render_footer, rule
from termi_word3.ui.layout import compute_frame_layout


@dataclass
class WordEntry:
    word: Word
    search_text: str
    status: str


def score_word_search(word_text: str, zh: str, search_text: str, query: str) -> int:
    """对单词搜索进行相关度匹配打分"""
    normalized_query = query.strip().lower()
    if not normalized_query:
        return 1
    word_lower = word_text.lower()
    if word_lower == normalized_query:
        return 10000
    if word_lower.startswith(normalized_query):
        return 8000 + len(normalized_query)
    zh_lower = zh.lower()
    if normalized_query in zh_lower:
        if zh_lower.startswith(normalized_query) or zh_lower == normalized_query:
            return 7500 + len(normalized_query)
        return 6000 - zh_lower.find(normalized_query)
    pos = search_text.find(normalized_query)
    if pos >= 0:
        return 5000 - pos + len(normalized_query) * 20
    return 0


class WordsScreen(Screen):
    """词表搜索与浏览屏幕，支持拼写匹配度打分与详细信息展开。"""
    
    can_focus = True

    def __init__(self, focus_search: bool = False, deck_id: int | None = None) -> None:
        super().__init__()
        self.focus_search_on_mount = focus_search
        self.deck_id = deck_id
        self.search_query = ""
        self.selected = 0
        self.list_offset = 0
        self.detail_scroll_x = 0
        self.detail_scroll_y = 0
        self.show_detail = True
        self.detail_selected = False
        self.starred_only = False
        self.entries: list[WordEntry] = []
        self.results: list[WordEntry] = []

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            with Horizontal(classes="input-row"):
                yield Static("> ", classes="input-prefix")
                yield Input(id="words-search-input", placeholder="键入进行实时搜索...")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.load_cache()
        self.apply_filter()
        self.render_words()
        if self.focus_search_on_mount:
            self.query_one("#words-search-input", Input).focus()

    def load_cache(self) -> None:
        """加载单词并混淆，若未指定 deck_id 则加载全库所有词本的全部单词进行全局搜索。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            if self.deck_id is not None:
                words = repo.list_words_with_cards(self.deck_id)
            else:
                words = repo.list_all_words_with_cards()
        self.entries = [
            WordEntry(
                word=word,
                search_text=self._search_text(word),
                status=self._mastery(word),
            )
            for word in words
        ]
        # 用日期作为随机种子，保证同一天乱序一致
        seed = int(date.today().strftime("%Y%m%d"))
        random.Random(seed).shuffle(self.entries)

    def apply_filter(self) -> None:
        """根据搜索字符串和收藏条件过滤候选单词，并限制搜索结果数量以防渲染卡顿。"""
        query = self.search_query.strip().lower()
        
        # 1. 过滤收藏
        filtered = self.entries
        if self.starred_only:
            filtered = [e for e in filtered if e.word.is_starred]

        # 2. 匹配过滤
        if not query:
            self.results = filtered
        else:
            scored = [(self._score(entry, query), entry) for entry in filtered]
            sorted_entries = [
                entry
                for score, entry in sorted(scored, key=lambda item: item[0], reverse=True)
                if score > 0
            ]
            self.results = sorted_entries[:200]

        # 重调选中项索引范围防止越界
        self.selected = min(self.selected, max(0, len(self.results) - 1))
        self.list_offset = min(self.list_offset, self.selected)

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
            has_input=True,
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
        self.render_words()

    def render_words(self) -> None:
        """渲染核心词表内容，详情支持纵向滚动。"""
        self_focus = self.query_one("#words-search-input", Input).has_focus
        
        # 实时动态配置 Footer 栏的提示信息
        if self_focus:
            footer_text = "键入搜索  Space/Enter 确认并锁定详情  Esc 退出搜索"
        elif self.detail_selected:
            footer_text = "↑↓ 滚动查看释义  ←→ 横向滚动  Esc 退出详情锁定"
        else:
            footer_text = "↑↓ 选词  Space/Enter 锁定详情  f 过滤收藏  Esc 返回"

        content_height, width = self.apply_dynamic_layout(footer_text)
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)
        mode_label = "Words / Search" if self_focus else "Words / Browse"
        if self.detail_selected:
            mode_label = "Words / Detail Locked"

        lines = [
            mode_label,
            rule(width=width),
        ]
        eff_height = max(1, content_height - 2)
        if self.show_detail and self.results:
            list_limit = max(1, eff_height // 2)
            max_detail = max(1, eff_height - list_limit - 1)
        else:
            list_limit = max(1, eff_height - 1)
            max_detail = 0

        visible = self.results[self.list_offset : self.list_offset + list_limit]
        for index, entry in enumerate(visible, start=self.list_offset):
            pointer = "> " if index == self.selected else "  "
            word = entry.word
            meaning = word.zh or word.core or word.en or ""
            star = "*" if word.is_starred else " "
            
            # 自适应宽度裁剪，以单词最大占宽比 16 位为例，如果宽度短，按比例裁剪
            w_w = max(10, min(16, width // 4))
            deck_tag = f"({word.deck.name})" if word.deck else ""
            
            # 转义各数据项以防止 Rich Markup 注入导致的样式泄露与文本吞没
            w_esc = escape(word.w)
            status_esc = escape(entry.status)
            star_esc = escape(star)
            deck_tag_esc = escape(deck_tag)
            c_esc = escape(word.c or '-')
            meaning_esc = escape(meaning)
            
            line_content = f"{pointer}{w_esc:<{w_w}} {status_esc:<4}{star_esc}{deck_tag_esc} \\[{c_esc}\\] {meaning_esc}"
            if index == self.selected:
                # 选中行背景高亮，文字高亮黄，底色深灰
                lines.append(f"[bold #FBBF24 on #1f2937]{line_content}[/]")
            else:
                lines.append(line_content)

        if not visible:
            lines.append("  无匹配单词结果")

        while len(lines) < list_limit:
            lines.append("")

        # 渲染底部详情或统计
        if self.show_detail and self.results:
            lines.append(rule(width=width))
            detail_all = self._detail_lines(self.results[self.selected].word)
            total = len(detail_all)
            if total > max_detail:
                self.detail_scroll_y = max(0, min(self.detail_scroll_y, total - max_detail))
                visible_detail = detail_all[self.detail_scroll_y : self.detail_scroll_y + max_detail]
                indicator = ""
                if self.detail_scroll_y > 0:
                    indicator += "↑"
                if self.detail_scroll_y + max_detail < total:
                    indicator += "↓"
                if indicator and visible_detail:
                    visible_detail[-1] = visible_detail[-1] + f" {indicator}"
            else:
                visible_detail = detail_all
            visible_detail = [line[self.detail_scroll_x:] for line in visible_detail]
            lines.extend(visible_detail)
        else:
            lines.append(
                f"  统计: 已筛选出 {len(self.results)} / {len(self.entries)} 个词"
            )

        content_widget.update(render_content_block(lines, height=content_height, width=width))

        # 刷新状态消息区
        msg_widget.remove_class("success", "error", "muted")
        
        if self_focus:
            msg_widget.add_class("muted")
            focus_status = "输入搜索中 | "
            detail_tip = "按 Enter 搜索"
        else:
            if self.detail_selected:
                msg_widget.add_class("success")
                focus_status = "已锁定详情 | "
                detail_tip = "按 ↑↓ 键上下滚动查看，按 Esc 退出锁定继续选词"
            else:
                msg_widget.add_class("muted")
                focus_status = "列表浏览 | "
                detail_tip = "按 Space/Enter 锁定详情进行滚动"
                
        msg_widget.update(f"{focus_status}{detail_tip}")

        footer_widget.update(render_footer(footer_text, width))

    def on_input_changed(self, event: Input.Changed) -> None:
        """输入内容变化时实时匹配过滤。"""
        if event.input.id == "words-search-input":
            self.search_query = event.value
            self.apply_filter()
            self.render_words()

    def on_key(self, event: Key) -> None:
        """键盘操作逻辑拦截。"""
        # 无条件放行全局搜索快捷键，避免被页面内 Key 消费吞掉
        if self.app.is_search_shortcut(event.key):
            event.stop()
            self.app.open_search()
            return

        # ? 键显示帮助
        if event.key in ("question_mark", "?"):
            event.stop()
            msg_widget = self.query_one("#message-area", Static)
            msg_widget.remove_class("success", "error")
            msg_widget.add_class("muted")
            msg_widget.update("快捷键: ↑↓ 选词 | Enter/Space 锁定详情 | 左右键滚动详情 | f 过滤收藏 | Esc 返回")
            return

        key = event.key
        inp = self.query_one("#words-search-input", Input)

        # 1. 退出本页或取消详情锁定
        if key == "escape":
            event.stop()
            if inp.has_focus:
                inp.blur()  # 失去焦点退出输入态
                self.focus()
                self.render_words()
            elif self.detail_selected:
                self.detail_selected = False
                self.detail_scroll_y = 0
                self.render_words()
            else:
                self.app.pop_screen()
            return

        # 2. 切换仅收藏过滤
        if key == "ctrl+f" or (key == "f" and not inp.has_focus):
            event.stop()
            self.starred_only = not self.starred_only
            self.apply_filter()
            self.render_words()
            return

        # 3. 向上：列表选择（未锁定） or 详情纵向滚动（已锁定）
        if key == "up":
            event.stop()
            if self.detail_selected:
                if self.detail_scroll_y > 0:
                    self.detail_scroll_y -= 1
                    self.render_words()
            else:
                self._move_selection(-1)
            return

        # 4. 向下：列表选择（未锁定） or 详情纵向滚动（已锁定）
        if key == "down":
            event.stop()
            if self.detail_selected:
                self.detail_scroll_y += 1
                self.render_words()
            else:
                self._move_selection(1)
            return

        # 5. 详情页左右横向滚动
        if key in ("left", "right"):
            if self.detail_selected:
                event.stop()
                delta = -1 if key == "left" else 1
                self.detail_scroll_x = max(0, self.detail_scroll_x + delta)
                self.render_words()
            return

        # 6. 回车/空格 锁定/解锁 详情展现
        if key in ("enter", "space"):
            event.stop()
            if inp.has_focus:
                inp.blur()
                self.focus()
                self.detail_selected = True
                self.detail_scroll_y = 0
            else:
                self.detail_selected = not self.detail_selected
                if not self.detail_selected:
                    self.detail_scroll_y = 0
            self.render_words()
            return

    def _move_selection(self, delta: int) -> None:
        """更改选中的卡片项。"""
        if not self.results:
            return
        self.selected = max(0, min(len(self.results) - 1, self.selected + delta))
        if self.selected < self.list_offset:
            self.list_offset = self.selected
        
        list_limit = 3 if self.show_detail else 6
        if self.selected >= self.list_offset + list_limit:
            self.list_offset = self.selected - list_limit + 1
        self.render_words()

    @staticmethod
    def _search_text(word: Word) -> str:
        return " ".join(
            [word.w or "", word.zh or "", word.core or "", word.en or "", word.c or ""]
        ).lower()

    @staticmethod
    def _score(entry: WordEntry, query: str) -> int:
        return score_word_search(
            entry.word.w,
            entry.word.zh or "",
            entry.search_text,
            query
        )

    @staticmethod
    def _mastery(word: Word) -> str:
        card = word.card
        if card is None or card.reps == 0:
            return "新词"
        if card.lapses:
            return "重学"
        if card.scheduled_days >= 21:
            return "掌握"
        if card.scheduled_days >= 3:
            return "记得"
        return "熟悉"

    @staticmethod
    def _detail_lines(word: Word) -> list[str]:
        """返回全部详情行，支持纵向滚动。"""
        lines = []
        star_lbl = r" \[已收藏\]" if word.is_starred else ""
        lines.append(f"  {escape(word.w)}  /{escape(word.us or '-')}/{star_lbl}")
        if word.core:
            lines.append(f"  Core: {escape(word.core)}")
        if word.zh:
            lines.append(f"  CN:   {escape(word.zh)}")
        if word.en:
            lines.append(f"  EN:   {escape(word.en)}")
        if word.ex:
            lines.append(f"  Ex:   {escape(word.ex)}")
        if word.exz:
            lines.append(f"        {escape(word.exz)}")
        return lines
