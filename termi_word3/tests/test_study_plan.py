"""学习计划设置生效回归测试。"""
from __future__ import annotations

import datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import close_all_sessions, sessionmaker

from termi_word3.database.models import Base, Deck, StudySession
from termi_word3.database.repositories import AppRepository


class TestStudyPlanSessions(unittest.TestCase):
    """验证学习计划变更后可以废弃旧的进行中队列。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        close_all_sessions()
        self.engine.dispose()

    def test_close_open_sessions_marks_active_sessions_completed(self) -> None:
        with self.session_factory() as session:
            deck = Deck(name="demo")
            session.add(deck)
            session.flush()
            open_session = StudySession(
                deck_id=deck.id,
                session_type="mixed",
                remaining_card_ids="[1, 2]",
                status=0,
                started_at=datetime.datetime(2026, 7, 10, 9, 0),
            )
            done_session = StudySession(
                deck_id=deck.id,
                session_type="mixed",
                remaining_card_ids="[]",
                status=1,
                started_at=datetime.datetime(2026, 7, 10, 8, 0),
            )
            session.add_all([open_session, done_session])
            session.commit()

            AppRepository(session).close_open_sessions(deck.id)
            session.commit()

            self.assertEqual(open_session.status, 1)
            self.assertEqual(done_session.status, 1)


if __name__ == "__main__":
    unittest.main()
