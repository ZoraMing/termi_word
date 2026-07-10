"""背词队列调度与学习进度会话管理服务"""
from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from termi_word3.database.models import Card, StudySession, Word
from termi_word3.database.repositories import AppRepository
from termi_word3.services.scheduler_service import SchedulerService
from termi_word3.domain.session_queue import SessionQueueIds
from termi_word3.domain.results import StudyActionResult


class StudyQueue:
    """背词卡片列表与会话信息的封装容器。"""

    def __init__(self, deck_id: int, cards: list[Card], session_id: int | None, is_extra: bool = False) -> None:
        self.deck_id = deck_id
        self.cards = cards
        self.session_id = session_id
        self.is_extra = is_extra


class StudyService:
    """提供学习和复习队列管理、断点恢复以及收藏挂起词的操作。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory
        self.scheduler = SchedulerService()

    def _get_future_due_cards(self, session, deck_id: int, limit: int) -> list[Card]:
        """抓取在未来最临近到期的复习单词，用于额外复习。"""
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        stmt = (
            select(Card)
            .join(Word)
            .options(joinedload(Card.word))
            .where(
                Word.deck_id == deck_id,
                Word.is_suspended.is_(False),
                Card.reps > 0,
            )
            .order_by(Card.due, Card.id)
            .limit(limit)
        )
        return list(session.execute(stmt).scalars())

    def build_today_queue(self, mode: str = "mixed") -> StudyQueue:
        """生成或恢复今日的背词学习卡片队列。"""
        with self.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            if deck is None:
                return StudyQueue(0, [], None)

            # 1. 尝试查找已存在的进行中会话 (断点恢复)
            study_session = repo.open_session(deck.id)
            if study_session is not None:
                queue_ids = SessionQueueIds.from_json(study_session.remaining_card_ids)
                cards = repo.cards_by_ids(list(queue_ids.ids))
                is_extra = study_session.session_type.startswith("extra_")
                return StudyQueue(deck.id, cards, study_session.id, is_extra=is_extra)

            # 2. 如果不存在，则根据配置构建全新队列
            setting = repo.get_settings()
            due_cards = repo.due_cards(deck.id, setting.review_soft_limit if mode != "new" else 0)
            new_cards = repo.new_cards(deck.id, setting.daily_new_target if mode != "review" else 0)

            # 按照学习顺序混合/排序
            mixed_cards = self._mix_cards(
                due_cards, new_cards, setting.study_order if mode == "mixed" else mode
            )

            is_extra = False
            # 如果按今日计划计算出的列表为空，自动进入“额外学习”模式（一直学，不被配置硬限制）
            if not mixed_cards:
                is_extra = True
                if mode == "new":
                    mixed_cards = repo.new_cards(deck.id, limit=20)
                elif mode == "review":
                    mixed_cards = self._get_future_due_cards(session, deck.id, limit=20)
                else:  # mixed
                    extra_new = repo.new_cards(deck.id, limit=10)
                    extra_due = self._get_future_due_cards(session, deck.id, limit=10)
                    mixed_cards = self._mix_cards(extra_due, extra_new, setting.study_order)

            # 创建会话
            study_session = StudySession(
                deck_id=deck.id,
                session_type=f"extra_{mode}" if is_extra else mode,
                remaining_card_ids=SessionQueueIds(tuple(c.id for c in mixed_cards)).to_json(),
                completed_count=0,
                status=0,
            )
            session.add(study_session)
            session.flush()

            session.commit()
            return StudyQueue(deck.id, mixed_cards, study_session.id, is_extra=is_extra)

    def rate_card(self, session_id: int | None, card_id: int, rating: int) -> StudyActionResult:
        """背词评分并自动持久化 FSRS 到数据库。"""
        with self.session_factory() as session:
            card = session.get(Card, card_id)
            if card is None:
                return StudyActionResult(card_id=card_id, rating=rating, scheduled_days=0, msg="单词不存在")

            # FSRS 调度计算并生成 ReviewLog
            log = self.scheduler.review(card, rating)
            session.add(log)

            # 更新今天会话进度
            if session_id is not None:
                study_session = session.get(StudySession, session_id)
                if study_session is not None:
                    queue_ids = SessionQueueIds.from_json(study_session.remaining_card_ids)
                    if card_id in queue_ids.ids:
                        new_queue = queue_ids.remove(card_id)
                        study_session.remaining_card_ids = new_queue.to_json()
                        study_session.completed_count += 1
                        if new_queue.is_empty:
                            study_session.status = 1  # 标记会话已完成

            session.commit()
            labels = {1: "陌生", 2: "熟悉", 3: "记得", 4: "掌握"}
            msg = f"评分: {labels.get(rating, str(rating))} | 下次复习: {card.scheduled_days}天后"
            return StudyActionResult(card_id=card_id, rating=rating, scheduled_days=card.scheduled_days, msg=msg)

    def toggle_star(self, word_id: int) -> bool:
        """收藏或取消收藏当前单词，返回最新状态。"""
        with self.session_factory() as session:
            word = session.get(Word, word_id)
            if word is None:
                return False
            word.is_starred = not word.is_starred
            session.commit()
            return word.is_starred

    def suspend_word(self, session_id: int | None, word_id: int) -> None:
        """挂起单词（暂停背诵模式），并将其立即从当前活动队列中剔除。"""
        with self.session_factory() as session:
            word = session.get(Word, word_id)
            if word is None:
                return
            word.is_suspended = True

            # 从当前会话队列中移除该卡片，防止用户之后刷新时再次学到它
            if session_id is not None and word.card is not None:
                card_id = word.card.id
                study_session = session.get(StudySession, session_id)
                if study_session is not None:
                    queue_ids = SessionQueueIds.from_json(study_session.remaining_card_ids)
                    if card_id in queue_ids.ids:
                        new_queue = queue_ids.remove(card_id)
                        study_session.remaining_card_ids = new_queue.to_json()
                        if new_queue.is_empty:
                            study_session.status = 1
            session.commit()

    def _mix_cards(self, due_cards: list[Card], new_cards: list[Card], order: str) -> list[Card]:
        """将到期卡片和新词卡片进行交叉或先后排序。"""
        if order == "review":
            return due_cards
        if order == "new":
            return new_cards
        if order == "new_first":
            return new_cards + due_cards
        if order == "review_first":
            return due_cards + new_cards

        # 默认 mixed: 3个复习卡搭配1个新词卡交叉呈现
        mixed: list[Card] = []
        due_idx, new_idx = 0, 0
        while due_idx < len(due_cards) or new_idx < len(new_cards):
            for _ in range(3):
                if due_idx < len(due_cards):
                    mixed.append(due_cards[due_idx])
                    due_idx += 1
            if new_idx < len(new_cards):
                mixed.append(new_cards[new_idx])
                new_idx += 1
        return mixed
