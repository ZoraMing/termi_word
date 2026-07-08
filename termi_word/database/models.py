from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    words: Mapped[list["Word"]] = relationship(back_populates="deck", cascade="all, delete-orphan")


class Word(Base):
    __tablename__ = "words"
    __table_args__ = (UniqueConstraint("deck_id", "normalized_word", name="uq_words_deck_normalized"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"), nullable=False, index=True)
    w: Mapped[str] = mapped_column(String(100), nullable=False)
    c: Mapped[str] = mapped_column(String(100), default="")
    zh: Mapped[str] = mapped_column(Text, default="")
    en: Mapped[str] = mapped_column(Text, default="")
    us: Mapped[str] = mapped_column(String(100), default="")
    core: Mapped[str] = mapped_column(Text, default="")
    ex: Mapped[str] = mapped_column(Text, default="")
    exz: Mapped[str] = mapped_column(Text, default="")
    normalized_word: Mapped[str] = mapped_column(String(100), nullable=False)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    deck: Mapped[Deck] = relationship(back_populates="words")
    card: Mapped["Card"] = relationship(back_populates="word", cascade="all, delete-orphan", uselist=False)

    @classmethod
    def from_csv_row(cls, deck_id: int, row: dict[str, str]) -> Word:
        """
        从 CSV 字典行数据构建并返回 Word 模型实例。
        进行必要的去空格等清洗操作以适配导入。
        """
        w_val = (row.get("w") or "").strip()
        return cls(
            deck_id=deck_id,
            w=w_val,
            c=(row.get("c") or "").strip(),
            zh=(row.get("zh") or "").strip(),
            en=(row.get("en") or "").strip(),
            us=(row.get("us") or "").strip(),
            core=(row.get("core") or "").strip(),
            ex=(row.get("ex") or "").strip(),
            exz=(row.get("exz") or "").strip(),
            normalized_word=w_val.lower(),
        )



class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), unique=True, nullable=False, index=True)
    state: Mapped[int] = mapped_column(Integer, default=1)
    step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    elapsed_days: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_days: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    word: Mapped[Word] = relationship(back_populates="card")
    logs: Mapped[list["ReviewLog"]] = relationship(back_populates="card", cascade="all, delete-orphan")


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[int] = mapped_column(Integer, nullable=False)
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    elapsed_days: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_days: Mapped[int] = mapped_column(Integer, default=0)
    review_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    card: Mapped[Card] = relationship(back_populates="logs")


class SpellingLog(Base):
    __tablename__ = "spelling_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), nullable=False, index=True)
    input_spelling: Mapped[str] = mapped_column(String(100), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hint_used_count: Mapped[int] = mapped_column(Integer, default=0)
    tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
