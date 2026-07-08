from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import ceil

from fsrs import State
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from termi_word.database.models import Card, Deck, ReviewLog, SpellingLog, Word, utc_now

_LEARNING_STATE = State.Learning.value


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    return start, end


@dataclass(frozen=True)
class TodayStats:
    deck_name: str
    total_words: int
    new_done: int
    daily_new_target: int
    review_done: int
    due_reviews: int
    remaining_new: int
    remaining_days: int


@dataclass(frozen=True)
class CalendarDay:
    day: date
    due_reviews: int
    reviewed: int


@dataclass(frozen=True)
class CalendarStats:
    days: list[CalendarDay]
    streak_days: int
    remaining_new: int
    remaining_days: int
    today_new: int
    today_review: int


class AppRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_deck(self, name: str) -> Deck:
        deck = self.session.scalar(select(Deck).where(Deck.name == name))
        if deck is not None:
            return deck
        deck = Deck(name=name)
        self.session.add(deck)
        self.session.flush()
        return deck

    def active_deck(self, name: str) -> Deck | None:
        return self.session.scalar(select(Deck).where(Deck.name == name))

    def has_words(self, deck_id: int) -> bool:
        return (self.session.scalar(select(func.count()).select_from(Word).where(Word.deck_id == deck_id)) or 0) > 0

    def add_word(self, deck: Deck, row: dict[str, str]) -> bool:
        word = (row.get("w") or "").strip()
        normalized = word.lower()
        if not normalized:
            return False
        exists = self.session.scalar(
            select(Word.id).where(Word.deck_id == deck.id, Word.normalized_word == normalized)
        )
        if exists:
            return False
        entity = Word.from_csv_row(deck.id, row)
        self.session.add(entity)
        self.session.flush()
        self.session.add(Card(word_id=entity.id, due=utc_now()))
        return True

    def today_stats(self, deck_name: str, daily_new_target: int) -> TodayStats:
        deck = self.active_deck(deck_name)
        if deck is None:
            return TodayStats(deck_name, 0, 0, daily_new_target, 0, 0, 0, 0)
        today = date.today()
        start, end = day_bounds(today)
        total_words = self.scalar_count(select(func.count()).select_from(Word).where(Word.deck_id == deck.id))
        new_done = self.scalar_count(
            select(func.count())
            .select_from(ReviewLog)
            .join(Card)
            .join(Word)
            .where(Word.deck_id == deck.id, ReviewLog.review_time.between(start, end), ReviewLog.state == _LEARNING_STATE)
        )
        review_done = self.scalar_count(
            select(func.count())
            .select_from(ReviewLog)
            .join(Card)
            .join(Word)
            .where(Word.deck_id == deck.id, ReviewLog.review_time.between(start, end), ReviewLog.state != _LEARNING_STATE)
        )
        due_reviews = self.scalar_count(
            select(func.count())
            .select_from(Card)
            .join(Word)
            .where(Word.deck_id == deck.id, Card.reps > 0, Card.due <= end)
        )
        remaining_new = self.scalar_count(
            select(func.count()).select_from(Card).join(Word).where(Word.deck_id == deck.id, Card.reps == 0)
        )
        remaining_days = ceil(remaining_new / daily_new_target) if daily_new_target > 0 else 0
        return TodayStats(deck.name, total_words, new_done, daily_new_target, review_done, due_reviews, remaining_new, remaining_days)

    def due_cards(self, deck_name: str, limit: int) -> list[Card]:
        deck = self.active_deck(deck_name)
        if deck is None:
            return []
        stmt = self.card_query(deck.id).where(Card.reps > 0, Card.due <= utc_now()).order_by(Card.due).limit(limit)
        return list(self.session.scalars(stmt))

    def new_cards(self, deck_name: str, limit: int) -> list[Card]:
        deck = self.active_deck(deck_name)
        if deck is None:
            return []
        stmt = self.card_query(deck.id).where(Card.reps == 0).order_by(Word.id).limit(limit)
        return list(self.session.scalars(stmt))

    def get_card(self, card_id: int) -> Card | None:
        return self.session.scalar(select(Card).options(joinedload(Card.word)).where(Card.id == card_id))

    def list_words(self, deck_name: str) -> list[Word]:
        deck = self.active_deck(deck_name)
        if deck is None:
            return []
        stmt = select(Word).where(Word.deck_id == deck.id).order_by(Word.w)
        return list(self.session.scalars(stmt))

    def word_by_id(self, word_id: int) -> Word | None:
        return self.session.scalar(select(Word).where(Word.id == word_id))

    def list_words_limited(self, deck_id: int, limit: int) -> list[Word]:
        stmt = select(Word).where(Word.deck_id == deck_id).order_by(Word.w).limit(limit)
        return list(self.session.scalars(stmt))

    def search_words(self, deck_id: int, query: str, limit: int) -> list[Word]:
        pattern = f"%{query}%"
        stmt = (
            select(Word)
            .where(Word.deck_id == deck_id, or_(
                Word.w.ilike(pattern),
                Word.c.ilike(pattern),
                Word.zh.ilike(pattern),
                Word.en.ilike(pattern),
                Word.core.ilike(pattern),
            ))
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def calendar_stats(self, deck_name: str, daily_new_target: int, anchor: date | None = None) -> CalendarStats:
        deck = self.active_deck(deck_name)
        today = anchor or date.today()
        if deck is None:
            return CalendarStats([], 0, 0, 0, 0, 0)
        start_day = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        end_day = next_month - timedelta(days=1)
        window_start, _ = day_bounds(start_day)
        _, window_end = day_bounds(end_day)

        # Single query: reviewed counts grouped by date
        reviewed_rows = self.session.execute(
            select(
                func.date(ReviewLog.review_time).label("day"),
                func.count().label("cnt"),
            )
            .join(Card, ReviewLog.card_id == Card.id)
            .join(Word, Card.word_id == Word.id)
            .where(Word.deck_id == deck.id, ReviewLog.review_time.between(window_start, window_end))
            .group_by(func.date(ReviewLog.review_time))
        ).all()
        reviewed_map: dict[str, int] = {row.day: row.cnt for row in reviewed_rows}

        # Single query: due card counts grouped by date
        due_rows = self.session.execute(
            select(
                func.date(Card.due).label("day"),
                func.count().label("cnt"),
            )
            .join(Word, Card.word_id == Word.id)
            .where(Word.deck_id == deck.id, Card.reps > 0, Card.due.between(window_start, window_end))
            .group_by(func.date(Card.due))
        ).all()
        due_map: dict[str, int] = {row.day: row.cnt for row in due_rows}

        days: list[CalendarDay] = []
        for index in range((end_day - start_day).days + 1):
            day = start_day + timedelta(days=index)
            day_str = day.isoformat()
            days.append(CalendarDay(day, due_map.get(day_str, 0), reviewed_map.get(day_str, 0)))

        # Aggregate today's stats from the same data
        today_str = today.isoformat()
        today_review = reviewed_map.get(today_str, 0)

        # remaining_new and total_words still need dedicated queries (can't derive from grouped data)
        remaining_new = self.scalar_count(
            select(func.count()).select_from(Card).join(Word).where(Word.deck_id == deck.id, Card.reps == 0)
        )
        remaining_days = ceil(remaining_new / daily_new_target) if daily_new_target > 0 else 0

        # Today's new count: reviews done today where state was Learning
        today_new = self.scalar_count(
            select(func.count())
            .select_from(ReviewLog)
            .join(Card)
            .join(Word)
            .where(Word.deck_id == deck.id, ReviewLog.review_time.between(window_start, window_end),
                   ReviewLog.state == _LEARNING_STATE, func.date(ReviewLog.review_time) == today_str)
        )

        return CalendarStats(
            days=days,
            streak_days=self.streak_days(deck.id, today),
            remaining_new=remaining_new,
            remaining_days=remaining_days,
            today_new=today_new,
            today_review=today_review,
        )

    def streak_days(self, deck_id: int, today: date, max_lookback: int = 365) -> int:
        lookback_start = today - timedelta(days=max_lookback)
        start_bound, _ = day_bounds(lookback_start)
        _, end_bound = day_bounds(today)
        rows = self.session.execute(
            select(func.date(ReviewLog.review_time).label("day"))
            .join(Card, ReviewLog.card_id == Card.id)
            .join(Word, Card.word_id == Word.id)
            .where(Word.deck_id == deck_id, ReviewLog.review_time.between(start_bound, end_bound))
            .group_by(func.date(ReviewLog.review_time))
        ).all()
        reviewed_dates = {row.day for row in rows}
        streak = 0
        current = today
        for _ in range(max_lookback + 1):
            if current.isoformat() not in reviewed_dates:
                break
            streak += 1
            current -= timedelta(days=1)
        return streak

    def spelling_candidates(self, deck_name: str, limit: int) -> list[Word]:
        deck = self.active_deck(deck_name)
        if deck is None:
            return []
        stmt = (
            select(Word)
            .join(Card)
            .where(Word.deck_id == deck.id, Card.reps > 0, Word.is_suspended.is_(False))
            .order_by(Card.last_review.desc().nullslast(), Word.id)
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def add_spelling_log(self, word_id: int, input_spelling: str, is_correct: bool, hint_used_count: int) -> None:
        self.session.add(
            SpellingLog(
                word_id=word_id,
                input_spelling=input_spelling,
                is_correct=is_correct,
                hint_used_count=hint_used_count,
                tested_at=utc_now(),
            )
        )

    def scalar_count(self, stmt: Select[tuple[int]]) -> int:
        return int(self.session.scalar(stmt) or 0)

    def card_query(self, deck_id: int) -> Select[tuple[Card]]:
        return select(Card).options(joinedload(Card.word)).join(Word).where(Word.deck_id == deck_id)
