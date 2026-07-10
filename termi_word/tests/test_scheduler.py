"""时区与调度单元测试"""
from __future__ import annotations

import datetime
import unittest

from termi_word.database.models import Card
from termi_word.services.scheduler_service import SchedulerService


class TestSchedulerTimezone(unittest.TestCase):
    """验证 FSRS 调度在处理数据库中 naive datetime 时的时区一致性。"""

    def setUp(self) -> None:
        self.scheduler_service = SchedulerService()

    def test_new_card_review(self) -> None:
        """测试新词卡片（last_review 为 None）时的 FSRS 调度。"""
        card = Card(
            id=999,
            state=0,
            due=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            last_review=None,
            reps=0,
            lapses=0,
        )
        log = self.scheduler_service.review(card, 3)  # Rating.Good
        self.assertIsNotNone(log)
        self.assertEqual(card.reps, 1)
        self.assertIsNotNone(card.last_review)

    def test_second_review_naive(self) -> None:
        """测试已复习过、last_review 为 naive datetime 的卡片在二次调度。"""
        card = Card(
            id=999,
            state=1,
            due=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            last_review=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=1),
            reps=1,
            lapses=0,
            stability=1.2,
            difficulty=3.1,
        )
        log = self.scheduler_service.review(card, 3)  # Rating.Good
        self.assertIsNotNone(log)
        self.assertEqual(card.reps, 2)

    def test_multiple_reviews_consecutively(self) -> None:
        """测试对同一个卡片连续多次打分（模拟很多输入）时是否崩溃。"""
        card = Card(
            id=777,
            state=0,
            due=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            last_review=None,
            reps=0,
            lapses=0,
        )
        
        # 第 1 次打分 (新词)
        log1 = self.scheduler_service.review(card, 3)
        self.assertEqual(card.reps, 1)
        self.assertIsNotNone(card.last_review)
        self.assertIsNone(card.last_review.tzinfo) # 数据库里的 last_review 必须是 naive
        
        # 第 2 次打分 (隔一会儿再次评分)
        log2 = self.scheduler_service.review(card, 3)
        self.assertEqual(card.reps, 2)
        
        # 第 3 次打分
        log3 = self.scheduler_service.review(card, 2)
        self.assertEqual(card.reps, 3)
        
        # 第 4 次打分
        log4 = self.scheduler_service.review(card, 4)
        self.assertEqual(card.reps, 4)

    def test_business_date_uses_configured_local_timezone(self) -> None:
        """业务日期应按用户配置的本地时区计算，而不是直接使用 UTC 日期。"""
        service = SchedulerService(
            now=lambda: datetime.datetime(2026, 7, 10, 17, 0, tzinfo=datetime.timezone.utc),
            timezone_offset_minutes=480,
        )

        due = datetime.datetime(2026, 7, 11, 1, 0)

        self.assertEqual(service.business_date(due), datetime.date(2026, 7, 11))
        self.assertEqual(service.scheduled_days_until(due), 0)
