"""学习/复习背词屏幕。"""
from __future__ import annotations

import asyncio
from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static

from termi_word3.database.models import Card
from termi_word3.ui import rule, render_content_block


class ReviewScreen(Screen):
    """卡片背诵页面，包含正面、背面翻卡以及 1-4 评分历史。"""

    BINDINGS = []  # 键盘由 on_key 统一控制以实现更细致的无焦点拦截

    def __init__(self, cards: list[Card], session_id: int | None) -> None:
        super().__init__()
        self.cards = cards
        self.session_id = session_id
        self.index = 0
        self.is_revealed = False
        self.feedback = ""
        self._waiting = False

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.render_card()

    @property
    def current_card(self) -> Card | None:
        """获取当前正在背诵的卡片，自动跳过被挂起的卡片。"""
        while self.index < len(self.cards):
            card = self.cards[self.index]
            if card.word and card.word.is_suspended:
                self.index += 1
            else:
                return card
        return None

    def render_card(self) -> None:
        """根据当前状态渲染 8 行核心内容和提示。"""
        card = self.current_card
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)

        # 1. 队列完成状态
        if card is None:
            lines = [
                "Termi Word / Complete",
                rule(),
                "",
                "      恭喜你！今日计划的学习队列已全部完成。",
                "",
                "      请按 Esc 键返回主界面。",
            ]
            content_widget.update(render_content_block(lines, height=8))
            msg_widget.update("")
            footer_widget.update("Esc 返回首页")
            return

        word = card.word
        progress = f"[{self.index + 1}/{len(self.cards)}]"
        star_flag = " *" if word.is_starred else ""

        # 2. 区分正面与背面
        if not self.is_revealed:
            # 正面：仅单词、音标、词性/分类
            us_str = f"/{word.us}/" if word.us else ""
            lines = [
                f"Termi Word / Learn  {progress}{star_flag}",
                rule(),
                f"  {word.w}",
                f"  {us_str}" if us_str else "",
                f"  [{word.c or '-'}]",
            ]
            content_widget.update(render_content_block(lines, height=8))
            if not self._waiting:
                msg_widget.update("按 Space 键翻卡以查看完整释义")
            footer_widget.update(self.app.ui_config.footer("review"))
        else:
            # 背面：单词头 + 详细释义
            us_str = f" /{word.us}/" if word.us else ""
            header = f"  {word.w}{us_str}  [{word.c or '-'}]"
            lines = [
                f"Termi Word / Revealed  {progress}{star_flag}",
                rule(),
                header,
            ]
            if word.core:
                lines.append(f"  Core: {word.core}")
            if word.zh:
                lines.append(f"  CN:   {word.zh}")
            if word.en:
                lines.append(f"  EN:   {word.en}")
            if word.ex:
                lines.append(f"  Ex:   {word.ex}")
            if word.exz:
                lines.append(f"        {word.exz}")

            content_widget.update(render_content_block(lines, height=8))
            if not self._waiting:
                msg_widget.update("请按 1-4 键评分: [1] 陌生  [2] 熟悉  [3] 记得  [4] 掌握")
            footer_widget.update(self.app.ui_config.footer("review"))

    def on_key(self, event: Key) -> None:
        """处理键盘事件。"""
        # 拦截全局 escape 以便在学习完成或中途退回
        if event.key == "escape":
            event.stop()
            self.app.pop_screen()
            return

        if self._waiting:
            # 如果正在等待自动切换，忽略其余交互按键
            return

        card = self.current_card
        if card is None:
            return

        key = event.key
        # Space 翻卡
        if key == "space":
            event.stop()
            if not self.is_revealed:
                self.is_revealed = True
                self.render_card()
            return

        # 1-4 评分
        if key in ("1", "2", "3", "4"):
            event.stop()
            rating = int(key)
            # 未翻卡亦可直接评分
            if not self.is_revealed:
                self.is_revealed = True
            feedback_str = self.app.study_service.rate_card(self.session_id, card.id, rating)
            self.query_one("#message-area", Static).update(f"已记录！{feedback_str}")
            self._waiting = True
            self.render_card()
            self.run_worker(self._auto_advance())
            return

        # f 收藏
        if key == "f":
            event.stop()
            starred = self.app.study_service.toggle_star(card.word.id)
            status_text = "已收藏此单词，将在右上角标记 *。" if starred else "已取消收藏该单词。"
            self.query_one("#message-area", Static).update(status_text)
            self.render_card()
            return

        # t 挂起
        if key == "t":
            event.stop()
            self.app.study_service.suspend_word(self.session_id, card.word.id)
            self.query_one("#message-area", Static).update("已挂起此单词。后续将不再调度复习。")
            self._waiting = True
            self.run_worker(self._auto_advance(immediate_ui_refresh=True))
            return

        # s 跳过
        if key == "s":
            event.stop()
            self.query_one("#message-area", Static).update("已跳过当前单词。")
            self._waiting = True
            self.run_worker(self._auto_advance(immediate_ui_refresh=True))
            return

    async def _auto_advance(self, immediate_ui_refresh: bool = False) -> None:
        """延迟 1.0 秒（除非是跳过/挂起即时刷新）后进入下一词。"""
        if not immediate_ui_refresh:
            await asyncio.sleep(1.0)
        self._waiting = False
        self.index += 1
        self.is_revealed = False
        self.render_card()
