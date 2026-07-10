"""学习/复习背词屏幕。"""
from __future__ import annotations

import asyncio
from textual.events import Key
from textual.widgets import Static

from termi_word3.database.models import Card
from termi_word3.database.repositories import AppRepository
from termi_word3.ui import TermiScreen
from termi_word3.ui.messages import format_study_action_result


class ReviewScreen(TermiScreen):
    """卡片背诵页面，包含正面、背面翻卡以及 1-4 评分历史。"""

    BINDINGS = []  # 键盘由 on_key 统一控制以实现更细致的无焦点拦截

    def __init__(self, cards: list[Card], session_id: int | None, is_extra: bool = False) -> None:
        super().__init__()
        self.cards = cards
        self.session_id = session_id
        self.index = 0
        self.is_revealed = False
        self.pending_action = None
        self.feedback = ""
        self.pending_rating: int | None = None
        self.content_scroll = 0
        self._has_extra_option = False
        self.is_extra = is_extra

    def on_mount(self) -> None:
        self.render_card()

    @property
    def current_card(self) -> Card | None:
        """获取当前正在背诵的卡片。"""
        if self.index >= len(self.cards):
            return None
        return self.cards[self.index]

    def render_card(self) -> None:
        """根据当前状态渲染核心内容和提示，支持自适应高宽与滚动。"""
        card = self.current_card

        # 1. 队列完成状态
        if card is None:
            # 检查是否有剩余新词或者未来要复习的卡片
            with self.app.session_factory() as session:
                repo = AppRepository(session)
                deck = repo.active_deck()
                has_extra = False
                if deck:
                    extra_cands = self.app.study_service._get_future_due_cards(session, deck.id, 1)
                    has_extra = (repo.remaining_new_count(deck.id) > 0 or len(extra_cands) > 0)
            
            if deck and has_extra:
                lines = [
                    "",
                    "      今日计划学习队列已全部完成！",
                    "",
                    "      按 Enter 键加载 20 个额外混合单词继续学习，",
                    "      或按 Esc 键返回主界面。",
                ]
                self._has_extra_option = True
                self.refresh_ui(
                    header="Review / Extra Option",
                    lines=lines,
                    message=self.feedback or "",
                    footer="Enter 额外学习  Esc 返回首页"
                )
                return
            else:
                lines = [
                    "",
                    "      恭喜你！今日计划的学习队列已全部完成。",
                    "",
                    "      请按 Esc 键返回主界面。",
                ]
                self._has_extra_option = False
                self.refresh_ui(
                    header="Review / Complete",
                    lines=lines,
                    message=self.feedback or "",
                    footer="Esc 返回首页"
                )
                return

        word = card.word
        progress = f"[{self.index + 1}/{len(self.cards)}]"
        star_flag = " *" if word.is_starred else ""

        # 2. 区分正面与背面
        if not self.is_revealed:
            # 正面：仅单词、音标、词性/分类
            us_str = f"/{word.us}/" if word.us else ""
            title_tag = "Review / Extra Front" if self.is_extra else "Review / Front"
            lines = [
                f"  {word.w}",
                f"  {us_str}" if us_str else "",
                f"  [{word.c or '-'}]",
            ]
            self.refresh_ui(
                header=f"{title_tag}  {progress}{star_flag}",
                lines=lines,
                message=self.feedback or "[正面] 请记忆单词，按 Space/Enter 翻卡，或按 1-4 快速评分",
                footer="Space 翻卡  1-4 评分  t 挂起  f 收藏  Esc 返回"
            )
        else:
            # 背面：生成全部内容行，支持纵向滚动
            us_str = f" /{word.us}/" if word.us else ""
            all_lines = [
                f"  {word.w}{us_str}  [{word.c or '-'}]",
            ]
            
            # 从 setting 加载展示开关
            with self.app.session_factory() as session:
                setting = AppRepository(session).get_settings()
            
            if word.core:
                all_lines.append(f"  Core: {word.core}")
            if word.zh:
                all_lines.append(f"  CN:   {word.zh}")
            if setting.show_en and word.en:
                all_lines.append(f"  EN:   {word.en}")
            if setting.show_examples and word.ex:
                all_lines.append(f"  Ex:   {word.ex}")
            if setting.show_examples and word.exz:
                all_lines.append(f"        {word.exz}")

            # 统一利用我们新写的基础 compute_dynamic_layout 得到可用视窗高度
            content_height, _ = self.compute_dynamic_layout()
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

            title_tag = "Review / Extra Revealed" if self.is_extra else "Review / Revealed"
            
            rating_names = {1: "陌生", 2: "熟悉", 3: "记得", 4: "掌握"}
            if self.pending_rating is not None:
                curr_name = rating_names.get(self.pending_rating, "未评分")
                msg = f"【当前评分：{curr_name}】 按 Space/Enter 确认并进入下一词，或按 1-4 修正"
            else:
                msg = "[背面] 请评分: [1] 陌生  [2] 熟悉  [3] 记得  [4] 掌握"
                
            self.refresh_ui(
                header=f"{title_tag}  {progress}{star_flag}",
                lines=visible,
                message=msg,
                footer="1-4 评分  Space/Enter 确认  t 挂起  f 收藏  Esc 返回"
            )

    def on_key(self, event: Key) -> None:
        """处理键盘事件。"""
        # 无条件放行全局搜索快捷键，避免被页面内 Key 消费吞掉
        if self.app.is_search_shortcut(event.key):
            event.stop()
            self.app.open_search()
            return

        # 处于待确认额外学习选项状态下按 Enter
        if getattr(self, "_has_extra_option", False) and event.key == "enter":
            event.stop()
            self._has_extra_option = False
            # 调用 build_today_queue 此时会自动拉取额外词
            queue = self.app.study_service.build_today_queue(mode="mixed")
            self.cards = queue.cards
            self.session_id = queue.session_id
            self.index = 0
            self.is_revealed = False
            self.pending_action = None
            self.is_extra = True
            self.feedback = "已进入额外学习模式！"
            self.render_card()
            return

        card = self.current_card
        if card is None:
            if event.key == "escape":
                event.stop()
                self.app.pop_screen()
            elif event.key == "enter":
                event.stop()
            return

        # 如果当前有挂起的二次确认动作
        if self.pending_action is not None:
            if event.key == self.pending_action.confirm_key:
                event.stop()
                action = self.pending_action.action
                self.pending_action = None
                if action == "suspend_word":
                    self.app.study_service.suspend_word(self.session_id, card.word.id)
                    self.feedback = "已挂起此单词。后续将不再调度复习。"
                    self.index += 1
                    self.is_revealed = False
                    self.pending_rating = None
                    self.content_scroll = 0
                self.render_card()
                return
            elif event.key == self.pending_action.cancel_key:
                event.stop()
                self.pending_action = None
                self.feedback = "已取消挂起。"
                self.render_card()
                return
            else:
                # 处于确认状态时，拦截其余键
                event.stop()
                return

        # 拦截全局 escape 以便退回
        if event.key == "escape":
            event.stop()
            self.app.pop_screen()
            return

        # ? 键显示帮助
        if event.key in ("question_mark", "?"):
            event.stop()
            self.feedback = "快捷键: Space/Enter 翻卡/确定 | 1-4 评分 | t 挂起 | f 收藏 | s 跳过 | Esc 返回"
            self.render_card()
            return



        key = event.key

        # 纵向滚动（翻卡背面且内容溢出时）
        if key == "up" and self.is_revealed:
            event.stop()
            if self.content_scroll > 0:
                self.content_scroll -= 1
                self.render_card()
            return
        if key == "down" and self.is_revealed:
            event.stop()
            self.content_scroll += 1
            self.render_card()
            return

        # Space/Enter 翻卡与确认存盘进入下一词
        if key in ("space", "enter"):
            event.stop()
            if not self.is_revealed:
                self.is_revealed = True
                self.content_scroll = 0
                self.render_card()
                return
            
            if self.pending_rating is not None:
                # 确认当前的评分，持久化并切换单词
                result = self.app.study_service.rate_card(self.session_id, card.id, self.pending_rating)
                self.feedback = f"已记录！{format_study_action_result(result)}"
                self.index += 1
                self.is_revealed = False
                self.pending_rating = None
                self.content_scroll = 0
                self.render_card()
            return

        # 1-4 评分（正面初评翻卡，背面修改评分，此时均不存盘）
        if key in ("1", "2", "3", "4"):
            event.stop()
            self.pending_rating = int(key)
            self.is_revealed = True
            self.feedback = ""
            self.render_card()
            return

        # f 收藏
        if key == "f":
            event.stop()
            starred = self.app.study_service.toggle_star(card.word.id)
            self.feedback = "已收藏此单词，将在右上角标记 *。" if starred else "已取消收藏该单词。"
            self.render_card()
            return

        # t 挂起 (需二次确认)
        if key == "t":
            event.stop()
            from termi_word3.ui.keyboard import PendingConfirmation, HIGH_IMPACT_ACTIONS
            self.pending_action = PendingConfirmation(
                action="suspend_word",
                prompt=HIGH_IMPACT_ACTIONS["suspend_word"]
            )
            self.feedback = self.pending_action.prompt
            self.render_card()
            return

        # s 跳过 (不经二阶段，直接即时切词)
        if key == "s":
            event.stop()
            self.query_one("#message-area", Static).update("已跳过当前单词。")
            self._waiting = True
            self.content_scroll = 0
            self.run_worker(self._auto_advance(immediate_ui_refresh=True))
            return

    async def _auto_advance(self, immediate_ui_refresh: bool = False) -> None:
        """延迟 1.0 秒（除非是跳过/挂起即时刷新）后进入下一词。"""
        if not immediate_ui_refresh:
            await asyncio.sleep(1.0)
        self._waiting = False
        self.index += 1
        self.is_revealed = False
        self.content_scroll = 0
        self.render_card()
