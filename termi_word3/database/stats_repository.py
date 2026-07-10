"""背词打卡统计与活动数据存取仓储。"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from termi_word3.database.models import ReviewLog, SpellingLog
from termi_word3.database.settings_repository import SettingsRepository
from termi_word3.services.time_service import timezone_from_offset


class StatsRepository:
    """负责今日学习总数、复习/新词占比、拼写测试及连续打卡统计"""

    def __init__(self, session: Session, settings_repository: SettingsRepository | None = None) -> None:
        self.session = session
        self.settings_repository = settings_repository

    def _timezone_offset_minutes(self) -> int:
        if self.settings_repository is None:
            return 0
        setting = self.settings_repository.get()
        return int(getattr(setting, "timezone_offset_minutes", 0) or 0)

    def _today(self) -> date:
        tz = timezone_from_offset(self._timezone_offset_minutes())
        return datetime.now(tz).date()

    def _utc_range_for_local_date(self, value: date) -> tuple[datetime, datetime]:
        tz = timezone_from_offset(self._timezone_offset_minutes())
        start = datetime.combine(value, time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
        end = datetime.combine(value, time.max, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
        return start, end

    def _local_date_from_utc_naive(self, value: datetime) -> date:
        tz = timezone_from_offset(self._timezone_offset_minutes())
        return value.replace(tzinfo=timezone.utc).astimezone(tz).date()

    def today_review_count(self) -> int:
        """获取今天复习单词的总次数 (包含新词与老词)。"""
        start, end = self._utc_range_for_local_date(self._today())
        stmt = select(func.count(ReviewLog.id)).where(
            and_(ReviewLog.review_time >= start, ReviewLog.review_time <= end)
        )
        return int(self.session.execute(stmt).scalar_one())

    def today_new_and_review_counts(self) -> tuple[int, int]:
        """获取今天背词的新词数与复习数。返回 (new_count, review_count)。"""
        start, end = self._utc_range_for_local_date(self._today())

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
        start, end = self._utc_range_for_local_date(self._today())
        stmt = select(func.count(SpellingLog.id)).where(
            and_(SpellingLog.tested_at >= start, SpellingLog.tested_at <= end)
        )
        return int(self.session.execute(stmt).scalar_one())

    def activity_dates(self) -> set[date]:
        """获取所有发生过背词或拼写的物理日期，返回去重集合。"""
        review_times = self.session.execute(select(ReviewLog.review_time)).scalars().all()
        spelling_times = self.session.execute(select(SpellingLog.tested_at)).scalars().all()
        return {
            self._local_date_from_utc_naive(value)
            for value in [*review_times, *spelling_times]
            if value is not None
        }

    def activity_dates_between(self, start_date: date, end_date: date) -> set[date]:
        """获取指定日期范围内发生过背词或拼写的日期。"""
        start, _ = self._utc_range_for_local_date(start_date)
        _, end = self._utc_range_for_local_date(end_date)
        review_times = self.session.execute(
            select(ReviewLog.review_time).where(
                and_(ReviewLog.review_time >= start, ReviewLog.review_time <= end)
            )
        ).scalars().all()
        spelling_times = self.session.execute(
            select(SpellingLog.tested_at).where(
                and_(SpellingLog.tested_at >= start, SpellingLog.tested_at <= end)
            )
        ).scalars().all()
        return {
            self._local_date_from_utc_naive(value)
            for value in [*review_times, *spelling_times]
            if value is not None
        }

    @staticmethod
    def _parse_activity_dates(raw_dates) -> set[date]:
        """将数据库 date()/Date 类型结果统一转换为 date 集合。"""
        values = set()
        for raw in raw_dates:
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
        current = self._today()
        streak = 0
        while current in values:
            streak += 1
            current = date.fromordinal(current.toordinal() - 1)
        return streak
