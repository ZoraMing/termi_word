"""拼写评测与日志服务"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload, sessionmaker

from termi_word3.database.models import Card, SpellingLog, Word
from termi_word3.database.repositories import AppRepository
from termi_word3.domain.results import SpellingResult


class SpellingService:
    """提供拼写练习题目生成及用户输入结果提交判定。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def candidates(self) -> list[Word]:
        """获取今日拼写测试的候选单词列表。"""
        with self.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            if deck is None:
                return []
            setting = repo.get_settings()
            # 拼写题目筛选: 未挂起、有复习进度(reps>0)、状态在复习/学习中的单词
            stmt = (
                select(Word)
                .join(Card)
                .options(joinedload(Word.card))
                .where(
                    Word.deck_id == deck.id,
                    Word.is_suspended.is_(False),
                    Card.reps > 0,
                    Card.state.in_([1, 2, 3]),  # 1: Learning, 2: Review, 3: Relearning
                )
                .order_by(Word.w)
                .limit(setting.daily_spelling_target)
            )
            return list(session.execute(stmt).scalars())

    def extra_candidates(self) -> list[Word]:
        """获取额外拼写测试候选词。"""
        from sqlalchemy import func
        with self.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck()
            if deck is None:
                return []
            stmt = (
                select(Word)
                .join(Card)
                .options(joinedload(Word.card))
                .where(
                    Word.deck_id == deck.id,
                    Word.is_suspended.is_(False),
                    Card.reps > 0,
                    Card.state.in_([1, 2, 3]),
                )
                .order_by(func.random())
                .limit(20)
            )
            return list(session.execute(stmt).scalars())

    def submit(self, word_id: int, spelling: str, hint_count: int) -> SpellingResult | None:
        """判定用户的拼写，并将拼写记录立即持久化到数据库，如果拼写错误则触发 FSRS 重学计划。"""
        with self.session_factory() as session:
            word = session.get(Word, word_id)
            if word is None:
                return None
            # 规范化空格和大小写校验
            is_correct = word.w.strip().lower() == spelling.strip().lower()
            log = SpellingLog(
                word_id=word.id,
                input_spelling=spelling,
                is_correct=is_correct,
                hint_used_count=hint_count,
            )
            session.add(log)
            
            # 记录错误次数并调整学习计划: 拼错时自动触发 FSRS 评分为 1 (重新学习)
            if not is_correct:
                card = word.card
                if card:
                    from termi_word3.services.scheduler_service import SchedulerService
                    scheduler = SchedulerService()
                    review_log = scheduler.review(card, 1)
                    session.add(review_log)

            session.commit()
            return SpellingResult(
                word_id=word.id,
                expected=word.w,
                typed=spelling,
                is_correct=is_correct,
                hint_used_count=hint_count,
            )
