"""SQLAlchemy 数据模型定义"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    """返回当前的 UTC 时间。"""
    return datetime.utcnow()


class Deck(Base):
    """词本模型"""
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    words = relationship("Word", back_populates="deck", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="deck", cascade="all, delete-orphan")


class Word(Base):
    """单词模型"""
    __tablename__ = "words"
    __table_args__ = (
        UniqueConstraint("deck_id", "normalized_word", name="uq_words_deck_normalized"),
        Index("ix_words_deck_normalized", "deck_id", "normalized_word"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    deck_id = Column(Integer, ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)
    w = Column(String(100), nullable=False)  # 单词拼写
    c = Column(String(100), nullable=True)   # 分类
    zh = Column(Text, nullable=True)         # 中文释义
    en = Column(Text, nullable=True)         # 英文定义
    us = Column(String(100), nullable=True)  # 音标
    core = Column(Text, nullable=True)       # 核心解释
    ex = Column(Text, nullable=True)         # 例句
    exz = Column(Text, nullable=True)        # 例句翻译
    normalized_word = Column(String(100), nullable=False, index=True)
    is_starred = Column(Boolean, default=False)
    is_suspended = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    deck = relationship("Deck", back_populates="words")
    card = relationship("Card", uselist=False, back_populates="word", cascade="all, delete-orphan")
    spelling_logs = relationship("SpellingLog", back_populates="word", cascade="all, delete-orphan")


class Card(Base):
    """卡片记忆状态模型 (FSRS)"""
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), unique=True, nullable=False)
    state = Column(Integer, default=0)  # 0: New, 1: Learning, 2: Review, 3: Relearning (py-fsrs默认)
    step = Column(Integer, nullable=True, default=0)
    stability = Column(Float, nullable=True)
    difficulty = Column(Float, nullable=True)
    elapsed_days = Column(Integer, default=0)
    scheduled_days = Column(Integer, default=0)
    reps = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    due = Column(DateTime, nullable=False, index=True, default=utc_now)
    last_review = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    word = relationship("Word", back_populates="card")
    review_logs = relationship("ReviewLog", back_populates="card", cascade="all, delete-orphan")


class ReviewLog(Base):
    """复习历史日志模型"""
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    state = Column(Integer, nullable=False)
    due = Column(DateTime, nullable=False)
    stability = Column(Float, nullable=True)
    difficulty = Column(Float, nullable=True)
    elapsed_days = Column(Integer, nullable=False, default=0)
    scheduled_days = Column(Integer, nullable=False, default=0)
    review_time = Column(DateTime, default=utc_now, index=True)

    card = relationship("Card", back_populates="review_logs")


class StudySession(Base):
    """学习会话模型 (保存当天进度)"""
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deck_id = Column(Integer, ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)
    session_type = Column(String(50), nullable=False)  # mixed, review, new
    current_word_id = Column(Integer, nullable=True)
    remaining_card_ids = Column(Text, nullable=True)   # JSON-serialized list of card IDs
    completed_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    review_count = Column(Integer, default=0)
    spelling_count = Column(Integer, default=0)
    status = Column(Integer, default=0)  # 0: in progress, 1: completed
    started_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    deck = relationship("Deck", back_populates="study_sessions")


class SpellingLog(Base):
    """拼写历史日志模型"""
    __tablename__ = "spelling_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    input_spelling = Column(String(100), nullable=True)
    is_correct = Column(Boolean, nullable=False)
    hint_used_count = Column(Integer, default=0)
    tested_at = Column(DateTime, default=utc_now, index=True)

    word = relationship("Word", back_populates="spelling_logs")


class Setting(Base):
    """全局设置模型"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    active_deck_id = Column(Integer, ForeignKey("decks.id", ondelete="SET NULL"), nullable=True)
    daily_new_target = Column(Integer, default=20)
    review_soft_limit = Column(Integer, default=100)
    daily_spelling_target = Column(Integer, default=15)
    spelling_enabled = Column(Boolean, default=True)
    spelling_mode = Column(String(30), default="daily")
    study_order = Column(String(30), default="mixed")
    show_us = Column(Boolean, default=True)
    show_en = Column(Boolean, default=True)
    show_examples = Column(Boolean, default=True)
    theme = Column(String(30), default="dark")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
