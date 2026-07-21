"""学习/复习背词屏幕。"""
from __future__ import annotations

import asyncio
from textual.events import Key
from textual.widgets import Static

from termi_word.database.models import Card
from termi_word.database.repositories import AppRepository
from termi_word.ui import TermiScreen, wrap_display, make_tui_progress_bar, safe_register_worker, safe_unregister_worker
from termi_word.ui.messages import format_study_action_result


class ReviewScreen(TermiScreen):
    """卡片背诵页面，包含正面、背面翻卡以及 1-4 评分历史。"""

    BINDINGS = []  # 键盘由 on_key 统一控制以实现更细致的无焦点拦截

    def __init__(self, cards: list[Card], session_id: int | None, is_extra: bool = False, mode: str = "mixed") -> None:
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
        self.mode = mode
        self._waiting = False
        self._auto_advance_worker = None
        self._extra_study_worker = None
        self._is_loading_extra = False
        self.is_busy = False
        self._rate_worker = None

    def on_mount(self) -> None:
        self.render_card()

    @property
    def current_card(self) -> Card | None:
        """获取当前正在背诵的卡片。"""
        if self.index >= len(self.cards):
            return None
        return self.cards[self.index]

    def _fetch_render_status(self, card_is_none: bool):
        """统一获取背词屏渲染所需的数据库状态。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            setting = repo.get_settings()
            if not deck:
                return None, setting, 0, 0, False

            today_new_left = repo.remaining_new_count(deck.id)
            today_rev_left = len(repo.due_cards(deck.id))
            has_extra = False

            if card_is_none:
                extra_cands = self.app.study_service._get_future_due_cards(session, deck.id, 1)
                if self.mode == "new":
                    has_extra = (today_new_left > 0)
                elif self.mode == "review":
                    has_extra = (len(extra_cands) > 0)
                else:  # mixed
                    has_extra = (today_new_left > 0 or len(extra_cands) > 0)

            return deck, setting, today_new_left, today_rev_left, has_extra

    def render_card(self) -> None:
        """根据当前状态渲染核心内容和提示，支持自适应高宽与滚动。"""
        card = self.current_card
        deck, setting, today_new_left, today_rev_left, has_extra = self._fetch_render_status(card is None)

        mode_zh = {"mixed": "学习", "new": "新词", "review": "复习"}.get(self.mode, "学习")
        prefix = "额外" if self.is_extra else ""

        # 1. 队列完成状态
        if card is None:
            if self._is_loading_extra:
                lines = [
                    "",
                    "      正在加载额外学习队列...",
                    "",
                    "      请稍候。",
                ]
                self._has_extra_option = False
                self.refresh_ui(
                    header=f"{prefix}{mode_zh} 加载额外",
                    lines=lines,
                    message=self.feedback or "",
                    footer="Esc 返回"
                )
                return

            if deck and has_extra:
                if self.mode == "new":
                    extra_type_str = "新词"
                elif self.mode == "review":
                    extra_type_str = "复习"
                else:
                    extra_type_str = "混合"
                lines = [
                    "",
                    "      今日计划学习队列已完成。",
                    "",
                    f"      按 Enter 键加载 {setting.daily_new_target} 个额外{extra_type_str}单词继续学习，",
                    "      或按 Esc 返回。",
                ]
                self._has_extra_option = True
                self.refresh_ui(
                    header=f"{prefix}{mode_zh} 继续",
                    lines=lines,
                    message=self.feedback or "",
                    footer="Enter 额外学习  Esc 返回"
                )
                return
            else:
                lines = [
                    "",
                    "      今日计划学习队列已完成。",
                    "",
                    "      按 Esc 返回。",
                ]
                self._has_extra_option = False
                self.refresh_ui(
                    header=f"{prefix}{mode_zh} 完成",
                    lines=lines,
                    message=self.feedback or "",
                    footer="Esc 返回"
                )
                return

        word = card.word
        # 计算当前队列中剩余的新词与复习词数
        rem_new = sum(1 for c in self.cards[self.index:] if c.reps == 0)
        rem_rev = sum(1 for c in self.cards[self.index:] if c.reps > 0)
        queue_detail = f" (新:{rem_new} 复:{rem_rev})" if len(self.cards) > 0 else ""
        
        bar = make_tui_progress_bar(self.index + 1, len(self.cards))
        progress = f"{bar} [{self.index + 1}/{len(self.cards)}]{queue_detail}"
        star_flag = " *" if word.is_starred else ""
        today_stats = f" | 待学: {today_new_left}新 {today_rev_left}复"

        # 2. 区分正面与背面
        if not self.is_revealed:
            # 正面：仅单词、音标、词性/分类
            us_str = f"/{word.us}/" if word.us else ""
            title_tag = f"{prefix}{mode_zh} 正面"
            lines = [
                f"  [#F59E0B]{word.w}[/]",
                f"  {us_str}" if us_str else "",
                f"  [{word.c or '-'}]",
            ]
            msg = self.feedback or "[正面] 请记忆单词，按 Space/Enter 翻卡，或按 1-4 快速评分"
            self.refresh_ui(
                header=f"{title_tag}  {progress}{star_flag}{today_stats}",
                lines=lines,
                message=msg,
                footer="Space 翻卡  1-4 评分  t 挂起  f 收藏  Esc 返回"
            )
        else:
            # 背面：生成全部内容行，支持自适应折行与纵向滚动
            content_height, width = self.compute_dynamic_layout()
            
            us_str = f" /{word.us}/" if word.us else ""
            header_text = f"  [#F59E0B]{word.w}[/]{us_str}  [{word.c or '-'}]"
            all_lines = []
            all_lines.extend(wrap_display(header_text, width=width, continuation_indent="  "))
            
            if word.core:
                all_lines.extend(wrap_display(f"  [#6B7280]Core:[/] {word.core}", width=width, continuation_indent="        "))
            if word.zh:
                all_lines.extend(wrap_display(f"  [#6B7280]CN:[/]   {word.zh}", width=width, continuation_indent="        "))
            if setting.show_en and word.en:
                all_lines.extend(wrap_display(f"  [#6B7280]EN:[/]   {word.en}", width=width, continuation_indent="        "))
            if setting.show_examples and word.ex:
                all_lines.extend(wrap_display(f"  [#6B7280]Ex:[/]   {word.ex}", width=width, continuation_indent="        "))
            if setting.show_examples and word.exz:
                all_lines.extend(wrap_display(f"        {word.exz}", width=width, continuation_indent="        "))

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

            title_tag = f"{prefix}{mode_zh} 背面"
            
            rating_names = {1: "陌生", 2: "熟悉", 3: "记得", 4: "掌握"}
            if self.pending_rating is not None:
                curr_name = rating_names.get(self.pending_rating, "未评分")
                msg = f"【当前评分：{curr_name}】 按 Space/Enter 确认并进入下一词，或按 1-4 修正"
            else:
                msg = "[背面] 请评分: [1] 陌生  [2] 熟悉  [3] 记得  [4] 掌握"
                
            self.refresh_ui(
                header=f"{title_tag}  {progress}{star_flag}{today_stats}",
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

        if self.is_busy:
            event.stop()
            return

        if event.key in ("question_mark", "?"):
            event.stop()
            self.toggle_footer()
            self.render_card()
            return

        # 处于待确认额外学习选项状态下按 Enter
        if getattr(self, "_has_extra_option", False) and event.key == "enter":
            event.stop()
            self._start_extra_study()
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
                    self._do_suspend_word(card)
                else:
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
                self._do_rate_card(self.pending_rating)
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
            self._do_toggle_star(card.word.id)
            return

        # t 挂起 (需二次确认)
        if key == "t":
            event.stop()
            from termi_word.ui.keyboard import PendingConfirmation, HIGH_IMPACT_ACTIONS
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
            self._do_auto_advance()
            return

    # ── 异步操作 ──────────────────────────────────────────────

    def _do_auto_advance(self) -> None:
        """跳过当前单词，即时切词。"""
        if self._waiting:
            return
        self._waiting = True
        self.content_scroll = 0
        if getattr(self, "is_mounted", True):
            self.query_one("#message-area", Static).update("已跳过当前单词。")
        self._auto_advance_worker = self.run_worker(
            self._async_auto_advance(immediate_ui_refresh=True),
            exclusive=True,
        )
        safe_register_worker(self, self._auto_advance_worker)

    def _start_extra_study(self) -> None:
        """后台构建额外学习队列。"""
        if self._extra_study_worker is not None or self._is_loading_extra:
            return
        self._has_extra_option = False
        self._is_loading_extra = True
        self.feedback = "正在加载额外学习队列..."
        self.render_card()
        self._extra_study_worker = self.run_worker(self._async_load_extra_study(), exclusive=True)
        safe_register_worker(self, self._extra_study_worker)

    def _do_rate_card(self, rating: int) -> None:
        """异步保存评分。"""
        if self.is_busy or self.current_card is None:
            return
        self.is_busy = True
        self.feedback = "正在保存评分..."
        self.render_card()
        self._rate_worker = self.run_worker(self._async_rate_card(rating), exclusive=True)
        safe_register_worker(self, self._rate_worker)

    def _do_suspend_word(self, card) -> None:
        """异步保存挂起状态。"""
        if self.is_busy:
            return
        self.is_busy = True
        self.feedback = "正在保存挂起状态..."
        self.render_card()
        self._rate_worker = self.run_worker(self._async_suspend_word(card), exclusive=True)
        safe_register_worker(self, self._rate_worker)

    def _do_toggle_star(self, word_id: int) -> None:
        """异步保存收藏状态。"""
        if self.is_busy:
            return
        self.is_busy = True
        self.feedback = "正在保存收藏状态..."
        self.render_card()
        self._rate_worker = self.run_worker(self._async_toggle_star(word_id), exclusive=True)
        safe_register_worker(self, self._rate_worker)

    async def _async_load_extra_study(self) -> None:
        """异步加载额外学习队列并刷新当前复习屏。"""
        try:
            queue = await asyncio.to_thread(self.app.study_service.build_today_queue, self.mode)
            self.cards = queue.cards
            self.session_id = queue.session_id
            self.index = 0
            self.is_revealed = False
            self.pending_action = None
            self.is_extra = True
            mode_zh = {"mixed": "学习", "new": "新词", "review": "复习"}.get(self.mode, "学习")
            self.feedback = f"已进入额外{mode_zh}模式。"
        except asyncio.CancelledError:
            self.feedback = "已取消加载额外学习。"
            raise
        except Exception as exc:
            self.feedback = f"加载额外学习失败: {exc}"
            self._has_extra_option = True
        finally:
            self._is_loading_extra = False
            safe_unregister_worker(self, self._extra_study_worker)
            self._extra_study_worker = None
            if getattr(self, "is_mounted", True):
                self.render_card()

    async def _async_auto_advance(self, immediate_ui_refresh: bool = False) -> None:
        """延迟 1.0 秒（除非是跳过/挂起即时刷新）后进入下一词。"""
        try:
            if not immediate_ui_refresh:
                await asyncio.sleep(1.0)
            self.index += 1
            self.is_revealed = False
            self.content_scroll = 0
            if getattr(self, "is_mounted", True):
                self.render_card()
        finally:
            self._waiting = False
            safe_unregister_worker(self, self._auto_advance_worker)
            self._auto_advance_worker = None

    async def _async_rate_card(self, rating: int) -> None:
        card = self.current_card
        try:
            result = await asyncio.to_thread(
                self.app.study_service.rate_card, self.session_id, card.id, rating
            )
            self.feedback = f"已记录！{format_study_action_result(result)}"
            self.index += 1
            self.is_revealed = False
            self.pending_rating = None
            self.content_scroll = 0
        except Exception as exc:
            self.feedback = f"保存评分失败: {exc}"
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._rate_worker)
            self._rate_worker = None
            if getattr(self, "is_mounted", True):
                self.render_card()

    async def _async_suspend_word(self, card) -> None:
        try:
            await asyncio.to_thread(
                self.app.study_service.suspend_word, self.session_id, card.word.id
            )
            self.feedback = "已挂起此单词。后续将不再调度复习。"
            self.index += 1
            self.is_revealed = False
            self.pending_rating = None
            self.content_scroll = 0
        except Exception as exc:
            self.feedback = f"挂起保存失败: {exc}"
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._rate_worker)
            self._rate_worker = None
            if getattr(self, "is_mounted", True):
                self.render_card()

    async def _async_toggle_star(self, word_id: int) -> None:
        try:
            starred = await asyncio.to_thread(self.app.study_service.toggle_star, word_id)
            self.feedback = "已收藏此单词，将在右上角标记 *。" if starred else "已取消收藏该单词。"
        except Exception as exc:
            self.feedback = f"收藏保存失败: {exc}"
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._rate_worker)
            self._rate_worker = None
            if getattr(self, "is_mounted", True):
                self.render_card()

    def on_unmount(self) -> None:
        """屏幕卸载时取消仍在运行的后台 worker。"""
        for attr in ("_auto_advance_worker", "_extra_study_worker", "_rate_worker"):
            worker = getattr(self, attr, None)
            if worker is not None:
                worker.cancel()
                setattr(self, attr, None)
        self._is_loading_extra = False
