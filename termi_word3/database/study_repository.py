"""学习/复习与卡片调度数据存取仓储。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from termi_word3.database.models import Card, StudySession, Word, ReviewLog


class StudyRepository:
    """负责复习卡片、学习会话、学习历史日志存取"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def due_cards(self, deck_id: int, limit: int | None = None) -> list[Card]:
        """获取已到期、未挂起的复习卡片。"""
        if limit == 0:
            return []
        stmt = (
            select(Card)
            .join(Word)
            .options(joinedload(Card.word))
            .where(
                Word.deck_id == deck_id,
                Word.is_suspended.is_(False),
                Card.reps > 0,
                Card.due <= datetime.now(timezone.utc).replace(tzinfo=None),
            )
            .order_by(Card.due, Card.id)
        )
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars())

    def new_cards(self, deck_id: int, limit: int) -> list[Card]:
        """获取全新 (reps=0)、未挂起的单词卡片。"""
        if limit == 0:
            return []
        stmt = (
            select(Card)
            .join(Word)
            .options(joinedload(Card.word))
            .where(
                Word.deck_id == deck_id,
                Word.is_suspended.is_(False),
                Card.reps == 0,
            )
            .order_by(Word.id)
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def cards_by_ids(self, card_ids: Iterable[int]) -> list[Card]:
        """根据卡片 ID 列表加载 FSRS 状态，并保持传入 the ID 顺序。"""
        ids = list(card_ids)
        if not ids:
            return []
        cards = self.session.execute(
            select(Card).options(joinedload(Card.word)).where(Card.id.in_(ids))
        ).scalars().all()
        by_id = {card.id: card for card in cards}
        return [by_id[cid] for cid in ids if cid in by_id]

    def open_session(self, deck_id: int, session_date: date | None = None) -> StudySession | None:
        """获取该词本当前活跃（进行中）的学习会话。"""
        filters = [StudySession.deck_id == deck_id, StudySession.status == 0]
        if session_date is not None:
            filters.append(StudySession.session_date == session_date)
        return self.session.execute(
            select(StudySession)
            .where(*filters)
            .order_by(StudySession.updated_at.desc())
        ).scalars().first()

    def close_open_sessions(self, deck_id: int) -> None:
        """关闭该词本当前所有进行中的学习会话。"""
        sessions = self.session.execute(
            select(StudySession).where(StudySession.deck_id == deck_id, StudySession.status == 0)
        ).scalars().all()
        for study_session in sessions:
            study_session.status = 1

    def remaining_new_count(self, deck_id: int) -> int:
        """统计词本中仍未背过的新词卡片总数。"""
        stmt = select(func.count(Card.id)).join(Word).where(Word.deck_id == deck_id, Card.reps == 0)
        return int(self.session.execute(stmt).scalar_one())

    def add_review_log(self, log: ReviewLog) -> None:
        """记录卡片复习历史"""
        self.session.add(log)
