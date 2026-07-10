"""统计仓储查询范围回归测试。"""
from __future__ import annotations

import datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from termi_word.database.models import Base, Card, Deck, ReviewLog, SpellingLog, Word
from termi_word.database.stats_repository import StatsRepository


class TestStatsRepository(unittest.TestCase):
    """验证日历活动日期可按日期范围查询。"""

    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_activity_dates_between_limits_review_and_spelling_dates(self) -> None:
        with self.session_factory() as session:
            deck = Deck(name="demo")
            word = Word(deck=deck, w="alpha", normalized_word="alpha")
            card = Card(word=word, due=datetime.datetime(2026, 7, 1))
            session.add_all([deck, word, card])
            session.flush()
            session.add_all([
                ReviewLog(
                    card_id=card.id,
                    rating=3,
                    state=1,
                    due=datetime.datetime(2026, 7, 1),
                    review_time=datetime.datetime(2026, 6, 30, 23, 59),
                ),
                ReviewLog(
                    card_id=card.id,
                    rating=3,
                    state=1,
                    due=datetime.datetime(2026, 7, 1),
                    review_time=datetime.datetime(2026, 7, 2, 10, 0),
                ),
                SpellingLog(
                    word_id=word.id,
                    input_spelling="alpha",
                    is_correct=True,
                    tested_at=datetime.datetime(2026, 7, 3, 9, 0),
                ),
                SpellingLog(
                    word_id=word.id,
                    input_spelling="alpha",
                    is_correct=True,
                    tested_at=datetime.datetime(2026, 8, 1, 0, 0),
                ),
            ])
            session.commit()

            values = StatsRepository(session).activity_dates_between(
                datetime.date(2026, 7, 1),
                datetime.date(2026, 7, 31),
            )

        self.assertEqual(values, {datetime.date(2026, 7, 2), datetime.date(2026, 7, 3)})


if __name__ == "__main__":
    unittest.main()
