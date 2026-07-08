"""数据访问仓储层，提供对 SQLite 数据库的高效查询与更新。"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Iterable
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from termi_word3.database.models import Card, Deck, ReviewLog, Setting, SpellingLog, StudySession, Word


def normalize_word(value: str) -> str:
    """去首尾空格，转小写，规范化多余空格。"""
    return " ".join(value.strip().lower().split())


class AppRepository:
    """Termi Word 统一数据存取层。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_settings(self) -> Setting:
        """获取或创建唯一的全局设置行。"""
        setting = self.session.execute(select(Setting).order_by(Setting.id)).scalars().first()
        if setting is None:
            setting = Setting()
            self.session.add(setting)
            self.session.flush()
        return setting

    def get_or_create_deck(self, name: str, description: str = "") -> Deck:
        """根据名称获取或创建词本。如果是第一个词本，自动设为活跃。"""
        deck = self.session.execute(select(Deck).where(Deck.name == name)).scalars().first()
        if deck is not None:
            return deck
        deck = Deck(name=name, description=description)
        self.session.add(deck)
        self.session.flush()

        setting = self.get_settings()
        if setting.active_deck_id is None:
            setting.active_deck_id = deck.id
        return deck

    def active_deck(self) -> Deck | None:
        """获取当前活跃的词本。如果未指定但存在词本，取第一个。"""
        setting = self.get_settings()
        if setting.active_deck_id:
            deck = self.session.get(Deck, setting.active_deck_id)
            if deck is not None:
                return deck
        deck = self.session.execute(select(Deck).order_by(Deck.id)).scalars().first()
        if deck is not None:
            setting.active_deck_id = deck.id
        return deck

    def word_count(self, deck_id: int | None = None) -> int:
        """统计词本中的单词总数。"""
        stmt = select(func.count(Word.id))
        if deck_id is not None:
            stmt = stmt.where(Word.deck_id == deck_id)
        return int(self.session.execute(stmt).scalar_one())

    def add_word_if_missing(self, deck: Deck, row: dict[str, str]) -> Word | None:
        """导入时若无重复单词则写入。自动创建关联卡片 (Card)。"""
        word_text = row.get("w", "").strip()
        if not word_text:
            return None
        normalized = normalize_word(word_text)
        existing = self.session.execute(
            select(Word).where(Word.deck_id == deck.id, Word.normalized_word == normalized)
        ).scalars().first()
        if existing is not None:
            return None

        word = Word(
            deck_id=deck.id,
            w=word_text,
            c=row.get("c") or "",
            zh=row.get("zh") or "",
            en=row.get("en") or "",
            us=row.get("us") or "",
            core=row.get("core") or "",
            ex=row.get("ex") or "",
            exz=row.get("exz") or "",
            normalized_word=normalized,
        )
        word.card = Card(due=datetime.utcnow())  # 默认到期以便立即被调度
        self.session.add(word)
        return word

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
                Card.due <= datetime.utcnow(),
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
        """根据卡片 ID 列表加载 FSRS 状态，并保持传入的 ID 顺序。"""
        ids = list(card_ids)
        if not ids:
            return []
        cards = self.session.execute(
            select(Card).options(joinedload(Card.word)).where(Card.id.in_(ids))
        ).scalars().all()
        by_id = {card.id: card for card in cards}
        return [by_id[cid] for cid in ids if cid in by_id]

    def search_words(
        self, query: str, deck_id: int | None = None, limit: int = 50, starred_only: bool = False
    ) -> list[Word]:
        """按关键字搜索单词、释义。可过滤仅收藏。"""
        stmt = select(Word)
        filters = []
        if query.strip():
            like = f"%{query.strip()}%"
            filters.append(
                or_(Word.w.like(like), Word.zh.like(like), Word.core.like(like), Word.en.like(like))
            )
        if deck_id is not None:
            filters.append(Word.deck_id == deck_id)
        if starred_only:
            filters.append(Word.is_starred.is_(True))

        if filters:
            stmt = stmt.where(and_(*filters))
        stmt = stmt.order_by(Word.w).limit(limit)
        return list(self.session.execute(stmt).scalars())

    def list_words_with_cards(self, deck_id: int) -> list[Word]:
        """加载词本下的所有单词及 FSRS 调度属性。"""
        return list(
            self.session.execute(
                select(Word)
                .options(joinedload(Word.card))
                .where(Word.deck_id == deck_id)
                .order_by(Word.id)
            ).scalars()
        )

    def remaining_new_count(self, deck_id: int) -> int:
        """统计词本中仍未背过的新词卡片总数。"""
        stmt = select(func.count(Card.id)).join(Word).where(Word.deck_id == deck_id, Card.reps == 0)
        return int(self.session.execute(stmt).scalar_one())

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
        # 注意 SQLite date() 返回的通常是字符串形式
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

    def open_session(self, deck_id: int) -> StudySession | None:
        """获取该词本当前活跃（进行中）的学习会话。"""
        return self.session.execute(
            select(StudySession)
            .where(StudySession.deck_id == deck_id, StudySession.status == 0)
            .order_by(StudySession.updated_at.desc())
        ).scalars().first()
