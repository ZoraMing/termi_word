"""数据访问仓储层，提供对 SQLite 数据库的高效查询与更新。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from termi_word3.database.models import Card, Deck, Setting, StudySession, Word
from termi_word3.database.settings_repository import SettingsRepository
from termi_word3.database.deck_repository import DeckRepository
from termi_word3.database.word_repository import WordRepository
from termi_word3.database.study_repository import StudyRepository
from termi_word3.database.stats_repository import StatsRepository


def normalize_word(value: str) -> str:
    """去首尾空格，转小写，规范化多余空格。"""
    return " ".join(value.strip().lower().split())


class AppRepository:
    """Termi Word 统一数据存取层 (过渡期 Facade 兼容层)。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings_repo = SettingsRepository(self.session)
        self.deck_repo = DeckRepository(self.session, self.settings_repo)
        self.word_repo = WordRepository(self.session)
        self.study_repo = StudyRepository(self.session)
        self.stats_repo = StatsRepository(self.session)

    def get_settings(self) -> Setting:
        """获取或创建唯一的全局设置行。"""
        return self.settings_repo.get()

    def get_or_create_deck(self, name: str, description: str = "") -> Deck:
        """根据名称获取或创建词本。如果是第一个词本，自动设为活跃。"""
        return self.deck_repo.get_or_create(name, description)

    def active_deck(self) -> Deck | None:
        """获取当前活跃的词本。如果未指定但存在词本，取第一个。"""
        return self.deck_repo.active()

    def word_count(self, deck_id: int | None = None) -> int:
        """统计词本中的单词总数。"""
        return self.word_repo.word_count(deck_id)

    def add_word_if_missing(self, deck: Deck, row: dict[str, str]) -> Word | None:
        """导入时若无重复单词则写入。自动创建关联卡片 (Card)。"""
        return self.word_repo.add_word_if_missing(deck, row)

    def due_cards(self, deck_id: int, limit: int | None = None) -> list[Card]:
        """获取已到期、未挂起的复习卡片。"""
        return self.study_repo.due_cards(deck_id, limit)

    def new_cards(self, deck_id: int, limit: int) -> list[Card]:
        """获取全新 (reps=0)、未挂起的单词卡片。"""
        return self.study_repo.new_cards(deck_id, limit)

    def cards_by_ids(self, card_ids: Iterable[int]) -> list[Card]:
        """根据卡片 ID 列表加载 FSRS 状态，并保持传入的 ID 顺序。"""
        return self.study_repo.cards_by_ids(card_ids)

    def search_words(
        self, query: str, deck_id: int | None = None, limit: int = 50, starred_only: bool = False
    ) -> list[Word]:
        """按关键字搜索单词、释义。可过滤仅收藏。"""
        return self.word_repo.search_words(query, deck_id, limit, starred_only)

    def list_words_with_cards(self, deck_id: int) -> list[Word]:
        """加载词本下的所有单词及 FSRS 调度属性，包含所属词书。"""
        return self.word_repo.list_words_with_cards(deck_id)

    def list_all_words_with_cards(self) -> list[Word]:
        """加载全量单词（跨所有词本）及 FSRS 调度属性与所属词书。"""
        return self.word_repo.list_all_words_with_cards()

    def remaining_new_count(self, deck_id: int) -> int:
        """统计词本中仍未背过的新词卡片总数。"""
        return self.study_repo.remaining_new_count(deck_id)

    def today_review_count(self) -> int:
        """获取今天复习单词的总次数 (包含新词与老词)。"""
        return self.stats_repo.today_review_count()

    def today_new_and_review_counts(self) -> tuple[int, int]:
        """获取今天背词的新词数与复习数。返回 (new_count, review_count)。"""
        return self.stats_repo.today_new_and_review_counts()

    def today_spelling_count(self) -> int:
        """获取今天拼写测试的次数。"""
        return self.stats_repo.today_spelling_count()

    def activity_dates(self) -> set[date]:
        """获取所有发生过背词或拼写的物理日期，返回去重集合。"""
        return self.stats_repo.activity_dates()

    def streak_days(self) -> int:
        """根据活动历史记录，计算当前连续背词打卡天数。"""
        return self.stats_repo.streak_days()

    def open_session(self, deck_id: int) -> StudySession | None:
        """获取该词本当前活跃（进行中）的学习会话。"""
        return self.study_repo.open_session(deck_id)

    def get_word_by_id(self, word_id: int) -> Word | None:
        """根据单词 ID 获取单词信息"""
        return self.word_repo.get_by_id(word_id)

    def upsert_word(self, deck: Deck, values: dict[str, str]) -> str:
        """插入或更新单词。返回 'inserted', 'updated', 或 'skipped'"""
        return self.word_repo.upsert_word(deck, values)
