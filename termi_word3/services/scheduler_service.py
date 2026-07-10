"""基于 FSRS 的卡片状态调度服务"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State

from termi_word3.database.models import Card, ReviewLog
from termi_word3.services.time_service import system_timezone_offset_minutes, timezone_from_offset


def default_local_now() -> datetime:
    """获取系统本地时区的当前时间。"""
    return datetime.now().astimezone()


class SchedulerService:
    """包装 py-fsrs 对卡片进行间隔调度的计算逻辑。"""

    def __init__(
        self,
        now: Callable[[], datetime] = default_local_now,
        timezone_offset_minutes: int | None = None,
    ) -> None:
        self.scheduler = Scheduler(enable_fuzzing=False)
        self.now = now
        self.timezone_offset_minutes = (
            system_timezone_offset_minutes(now())
            if timezone_offset_minutes is None
            else int(timezone_offset_minutes)
        )

    def review(self, card: Card, rating_value: int) -> ReviewLog:
        """根据用户评分更新 FSRS 卡片记忆属性，并返回关联的历史日志。"""
        rating = Rating(rating_value)
        before_state = card.state
        before_due = card.due
        before_reps = card.reps
        before_last_review = card.last_review

        fsrs_card = self._to_fsrs_card(card)
        current_time = self._now_utc()
        
        # 显式传入带时区的当前时间，防止 scheduler.review_card 内部因默认时区造成 offset 错误
        reviewed_card, _fsrs_log = self.scheduler.review_card(fsrs_card, rating, current_time)

        self._apply_fsrs_card(card, reviewed_card, before_last_review)

        card.reps = before_reps + 1
        if rating_value == Rating.Again.value:
            card.lapses += 1

        return ReviewLog(
            card_id=card.id,
            rating=rating_value,
            state=before_state,
            due=before_due,
            stability=card.stability,
            difficulty=card.difficulty,
            elapsed_days=card.elapsed_days,
            scheduled_days=card.scheduled_days,
            review_time=current_time.astimezone(timezone.utc).replace(tzinfo=None),
        )

    def _to_fsrs_card(self, card: Card) -> FsrsCard:
        """将 SQLAlchemy 的 Card 模型转换成 FSRS 内部支持的卡片对象。"""
        # State 枚举只支持 1, 2, 3, 4，不支持 0 (0为数据库未背的初始默认值，映射为 1 即 State.New)
        state = card.state if card.state in (1, 2, 3, 4) else 1
        stability = None if card.reps == 0 and not card.stability else card.stability
        difficulty = None if card.reps == 0 and not card.difficulty else card.difficulty
        
        # 使用极其稳健的 to_utc_aware 归一化时区信息
        due = self._to_utc_aware(card.due)
        last_review = self._to_utc_aware(card.last_review)

        return FsrsCard(
            card_id=card.id,
            state=State(state),
            step=card.step,
            stability=stability,
            difficulty=difficulty,
            due=due,
            last_review=last_review,
        )

    def _to_utc_aware(self, dt: datetime | None) -> datetime | None:
        """辅助函数：安全地将任何 naive 或 aware datetime 统一转换为 UTC aware datetime。"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _now_utc(self) -> datetime:
        """返回 FSRS 要求的 UTC aware 当前时间。"""
        value = self.now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone_from_offset(self.timezone_offset_minutes))
        return value.astimezone(timezone.utc)

    def business_date(self, dt: datetime | None = None) -> date:
        """按用户本地时区换算业务日期。数据库 naive datetime 视为 UTC 存储。"""
        value = dt or self.now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone_from_offset(self.timezone_offset_minutes)).date()

    def scheduled_days_until(self, due: datetime) -> int:
        """按本地业务日期计算到期天数。"""
        return max(0, (self.business_date(due) - self.business_date()).days)

    def _apply_fsrs_card(self, target: Card, source: FsrsCard, before_last_review: datetime | None) -> None:
        """将 FSRS 卡片属性回填应用到 SQLAlchemy 的卡片模型中，彻底剥离时区存回 SQLite。"""
        target.state = int(source.state.value)
        target.step = source.step
        target.stability = source.stability
        target.difficulty = source.difficulty
        
        # 去掉时区信息，保持 sqlite 时区纯净为 naive
        target.due = source.due.replace(tzinfo=None) if source.due and source.due.tzinfo else source.due
        target.last_review = (
            source.last_review.replace(tzinfo=None)
            if source.last_review and source.last_review.tzinfo
            else source.last_review
        )
        
        # 提取 date 防止类型混淆相减
        current_time = self.now()
        if before_last_review:
            target.elapsed_days = max(0, (self.business_date(current_time) - self.business_date(before_last_review)).days)
        else:
            target.elapsed_days = 0
            
        target.scheduled_days = self.scheduled_days_until(target.due)
