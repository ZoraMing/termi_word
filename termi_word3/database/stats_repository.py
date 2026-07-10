"""背词打卡统计与活动数据存取仓储。"""
from __future__ import annotations

from datetime import date, datetime, time
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from termi_word3.database.models import ReviewLog, SpellingLog


class StatsRepository:
    """负责今日学习总数、复习/新词占比、拼写测试及连续打卡统计"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def today_review_count(self) -> int:
        """获取今天复习单词的总次数 (包含新词与老词)。"""
        start = datetime.combine(date.today(), time.min)
        end = datetime.combine(date.today(), time.max)
        stmt = select(func.count(ReviewLog.id)).where(
            and_(ReviewLog.review_time >= start, ReviewLog.review_time <= end)
        )
        return int(self.session.execute(stmt).scalar_one())

    def today_new_and_review_counts(self) -> tuple[int, int]:
        """获取今天背词的新词数与复习数。返回 (new_count, review_count)。"""
        start = datetime.combine(date.today(), time.min)
        end = datetime.combine(date.today(), time.max)

        # 统计新词 (打分前的状态是 0 或 1 即 State.New)
        stmt_new = select(func.count(ReviewLog.id)).where(
            and_(
                ReviewLog.review_time >= start,
                ReviewLog.review_time <= end,
                ReviewLog.state.in_([0, 1])
            )
        )
        new_cnt = int(self.session.execute(stmt_new).scalar_one())

        # 统计复习词 (打分前的状态是 2: Learning, 3: Review, 4: Relearning 之一)
        stmt_rev = select(func.count(ReviewLog.id)).where(
            and_(
                ReviewLog.review_time >= start,
                ReviewLog.review_time <= end,
                ReviewLog.state.in_([2, 3, 4])
            )
        )
        rev_cnt = int(self.session.execute(stmt_rev).scalar_one())

        return new_cnt, rev_cnt

    def today_spelling_count(self) -> int:
        """获取今天拼写测试的次数。"""
        start = datetime.combine(date.today(), time.min)
        end = datetime.combine(date.today(), time.max)
        stmt = select(func.count(SpellingLog.id)).where(
            and_(SpellingLog.tested_at >= start, SpellingLog.tested_at <= end)
        )
        return int(self.session.execute(stmt).scalar_one())

    def activity_dates(self) -> set[date]:
        """获取所有发生过背词或拼写的物理日期，返回去重集合。"""
        review_dates = self.session.execute(select(func.date(ReviewLog.review_time))).scalars().all()
        spelling_dates = self.session.execute(select(func.date(SpellingLog.tested_at))).scalars().all()
        values = set()
        for raw in [*review_dates, *spelling_dates]:
            if not raw:
                continue
            if isinstance(raw, str):
                values.add(date.fromisoformat(raw))
            elif isinstance(raw, date):
                values.add(raw)
        return values

    def streak_days(self) -> int:
        """根据活动历史记录，计算当前连续背词打卡天数。"""
        values = self.activity_dates()
        current = date.today()
        streak = 0
        while current in values:
            streak += 1
            current = date.fromordinal(current.toordinal() - 1)
        return streak
