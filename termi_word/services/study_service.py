from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State
from sqlalchemy.orm import Session, sessionmaker

from termi_word.database.models import Card, ReviewLog
from termi_word.database.repositories import AppRepository


@dataclass(frozen=True)
class ReviewPreview:
    rating: int
    feedback: str
    due: datetime


class StudyService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.scheduler = Scheduler()

    def build_queue(self, deck_name: str, mode: str, daily_new_target: int, review_limit: int) -> list[Card]:
        with self.session_factory() as session:
            repo = AppRepository(session)
            if mode == "review":
                return repo.due_cards(deck_name, review_limit)
            if mode == "new":
                return repo.new_cards(deck_name, daily_new_target)
            due = repo.due_cards(deck_name, review_limit)
            new_limit = max(0, daily_new_target - len(due))
            return due + repo.new_cards(deck_name, new_limit)

    def preview(self, card: Card, rating: int) -> ReviewPreview:
        scheduled, _ = self.scheduler.review_card(self.to_fsrs(card), Rating(rating))
        return ReviewPreview(rating=rating, feedback=self.feedback_text(scheduled.due), due=scheduled.due)

    def commit(self, card_id: int, rating: int) -> str:
        with self.session_factory() as session:
            repo = AppRepository(session)
            card = repo.get_card(card_id)
            if card is None:
                return "卡片不存在"
            before_state = card.state
            scheduled, _ = self.scheduler.review_card(self.to_fsrs(card), Rating(rating))
            self.apply_fsrs(card, scheduled)
            card.reps += 1
            if rating == Rating.Again.value:
                card.lapses += 1
            session.add(
                ReviewLog(
                    card_id=card.id,
                    rating=rating,
                    state=before_state,
                    due=card.due,
                    stability=card.stability,
                    difficulty=card.difficulty,
                    elapsed_days=card.elapsed_days,
                    scheduled_days=card.scheduled_days,
                    review_time=datetime.now(timezone.utc),
                )
            )
            session.commit()
            return self.feedback_text(card.due)

    def to_fsrs(self, card: Card) -> FsrsCard:
        return FsrsCard(
            card_id=card.id,
            state=State(card.state),
            step=card.step,
            stability=card.stability,
            difficulty=card.difficulty,
            due=self.ensure_aware(card.due),
            last_review=self.ensure_aware(card.last_review) if card.last_review else None,
        )

    def apply_fsrs(self, card: Card, scheduled: FsrsCard) -> None:
        now = datetime.now(timezone.utc)
        card.state = scheduled.state.value
        card.step = scheduled.step
        card.stability = scheduled.stability
        card.difficulty = scheduled.difficulty
        card.due = scheduled.due
        card.last_review = scheduled.last_review or now
        delta = card.due - now
        card.scheduled_days = max(0, delta.days)
        card.elapsed_days = 0

    def feedback_text(self, due: datetime) -> str:
        now = datetime.now(timezone.utc)
        delta = due - now
        if delta.days > 0:
            return f"{delta.days} 天后复习"
        minutes = max(1, int(delta.total_seconds() // 60))
        return f"{minutes} 分钟后复习"

    def ensure_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
