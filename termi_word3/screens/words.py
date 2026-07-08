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

from termi_word3.database.models import Word
from termi_word3.database.repositories import AppRepository
from termi_word3.ui import rule, render_content_block


@dataclass
class WordEntry:
    word: Word
    search_text: str
    status: str


class WordsScreen(Screen):
    """词表搜索与浏览屏幕，支持拼写匹配度打分与详细信息展开。"""

    def __init__(self, focus_search: bool = False) -> None:
        super().__init__()
        self.focus_search_on_mount = focus_search
        self.search_query = ""
        self.selected = 0
        self.list_offset = 0
        self.detail_scroll = 0
        self.show_detail = False
        self.starred_only = False
        self.entries: list[WordEntry] = []
        self.results: list[WordEntry] = []

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            with Horizontal(classes="input-row"):
                yield Static("搜索 > ", classes="input-prefix")
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
        """加载当前活跃词本的所有单词并混淆。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            words = repo.list_words_with_cards(deck.id) if deck else []
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
        """根据搜索字符串和收藏条件过滤候选单词。"""
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
            self.results = [
                entry
                for score, entry in sorted(scored, key=lambda item: item[0], reverse=True)
                if score > 0
            ]

        # 重调选中项索引范围防止越界
        self.selected = min(self.selected, max(0, len(self.results) - 1))
        self.list_offset = min(self.list_offset, self.selected)

    def render_words(self) -> None:
        """渲染核心 7 行词表内容。"""
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)

        # 列表最大行数计算：总高 7 行。
        # 如果详情展开，详情区占用 3 行，分割线 1 行，则列表展示区只剩 3 行。
        # 如果未展开，列表展示区占 6 行，统计占 1 行。
        lines = []
        if self.show_detail and self.results:
            list_limit = 3
        else:
            list_limit = 6

        visible = self.results[self.list_offset : self.list_offset + list_limit]
        for index, entry in enumerate(visible, start=self.list_offset):
            pointer = "> " if index == self.selected else "  "
            word = entry.word
            meaning = word.zh or word.core or word.en or ""
            star = "*" if word.is_starred else " "
            # 对齐格式化行
            lines.append(f"{pointer}{word.w:<16} {entry.status:<4}{star} [{word.c or '-'}] {meaning}")

        if not visible:
            lines.append("  无匹配单词结果")

        # 填充行高到 list_limit
        while len(lines) < list_limit:
            lines.append("")

        # 渲染底部详情或统计
        if self.show_detail and self.results:
            lines.append(rule())
            detail_all = self._detail_lines(self.results[self.selected].word)
            # 详情可见 3 行，可横向滚动
            visible_detail = detail_all[self.detail_scroll : self.detail_scroll + 3]
            lines.extend(visible_detail)
        else:
            lines.append(
                f"  统计: 已筛选出 {len(self.results)} / {len(self.entries)} 个词"
            )

        content_widget.update(render_content_block(lines, height=7))
        
        # 刷新状态消息区
        filter_status = "【仅显示收藏*】" if self.starred_only else ""
        self_focus = self.query_one("#words-search-input", Input).has_focus
        focus_status = "输入中 | " if self_focus else "列表聚焦 (按 Tab 聚焦输入) | "
        msg_widget.update(f"{focus_status}{filter_status}按 ctrl+f 切换收藏过滤")
        
        footer_widget.update(self.app.ui_config.footer("words"))

    def on_input_changed(self, event: Input.Changed) -> None:
        """输入内容变化时实时匹配过滤。"""
        if event.input.id == "words-search-input":
            self.search_query = event.value
            self.apply_filter()
            self.render_words()

    def on_key(self, event: Key) -> None:
        """键盘操作逻辑拦截。"""
        key = event.key
        inp = self.query_one("#words-search-input", Input)

        # 0. 键盘重新搜索 (清空 & 聚焦)
        if key in ("ctrl+slash", "ctrl+/"):
            event.stop()
            inp.value = ""
            self.search_query = ""
            self.apply_filter()
            inp.focus()
            self.render_words()
            return

        # 1. 退出本页
        if key == "escape":
            event.stop()
            if inp.has_focus:
                inp.screen_blur()  # 失去焦点退出输入态
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

        # 3. 向上滚动列表
        if key == "up":
            event.stop()
            self._move_selection(-1)
            return

        # 4. 向下滚动列表
        if key == "down":
            event.stop()
            self._move_selection(1)
            return

        # 5. 详情页翻页/左右滚动
        if key in ("left", "right"):
            if self.show_detail:
                event.stop()
                delta = -1 if key == "left" else 1
                self.detail_scroll = max(0, self.detail_scroll + delta)
                self.render_words()
            return

        # 6. 回车/空格 切换详情展现
        if key in ("enter", "space"):
            event.stop()
            self.show_detail = not self.show_detail
            self.detail_scroll = 0
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
        w_low = entry.word.w.lower()
        if w_low == query:
            return 10000
        if w_low.startswith(query):
            return 8000 + len(query)
        pos = entry.search_text.find(query)
        if pos >= 0:
            return 5000 - pos + len(query) * 20
        return 0

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
        """返回 3 行展开的精炼详情段落。"""
        lines = []
        star_lbl = " [已收藏]" if word.is_starred else ""
        lines.append(f"  定义: {word.w}  /{word.us or '-'}/{star_lbl}")
        lines.append(f"  释义: {word.zh or word.core or '-'}")
        if word.ex:
            lines.append(f"  例句: {word.ex} ({word.exz or ''})")
        else:
            lines.append(f"  英文: {word.en or '-'}")
        return lines
