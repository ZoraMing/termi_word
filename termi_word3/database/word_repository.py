"""单词数据存取仓储。"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload
from termi_word3.database.models import Card, Deck, Word


def normalize_word(value: str) -> str:
    """去首尾空格，转小写，规范化多余空格。"""
    return " ".join(value.strip().lower().split())


class WordRepository:
    """负责单词的查询、搜索、导入添加与更新(upsert)"""

    def __init__(self, session: Session) -> None:
        self.session = session

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
        word.card = Card(due=datetime.now(timezone.utc).replace(tzinfo=None))  # 默认到期以便立即被调度
        self.session.add(word)
        return word

    def search_words(
        self, query: str, deck_id: int | None = None, limit: int = 200, starred_only: bool = False
    ) -> list[Word]:
        """按关键字搜索单词、释义。可过滤仅收藏。预加载 card/deck 关联。"""
        stmt = select(Word).options(joinedload(Word.card), joinedload(Word.deck))
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
        return list(self.session.execute(stmt).scalars().unique())

    def list_words_with_cards(self, deck_id: int) -> list[Word]:
        """加载词本下的所有单词及 FSRS 调度属性，包含所属词书。"""
        return list(
            self.session.execute(
                select(Word)
                .options(joinedload(Word.card), joinedload(Word.deck))
                .where(Word.deck_id == deck_id)
                .order_by(Word.id)
            ).scalars()
        )

    def list_all_words_with_cards(self) -> list[Word]:
        """加载全量单词（跨所有词本）及 FSRS 调度属性与所属词书。"""
        return list(
            self.session.execute(
                select(Word)
                .options(joinedload(Word.card), joinedload(Word.deck))
                .order_by(Word.id)
            ).scalars()
        )

    def get_by_id(self, word_id: int) -> Word | None:
        """根据单词 ID 获取单词信息"""
        return self.session.get(Word, word_id)

    def upsert_word(self, deck: Deck, values: dict[str, str]) -> str:
        """插入或更新单词。返回 'inserted', 'updated', 或 'skipped'"""
        word_text = values.get("w", "").strip()
        if not word_text:
            return "skipped"

        normalized = normalize_word(word_text)
        existing = self.session.execute(
            select(Word).where(Word.deck_id == deck.id, Word.normalized_word == normalized)
        ).scalars().first()

        if existing is not None:
            # 更新现有单词
            for field in ["c", "zh", "en", "us", "core", "ex", "exz"]:
                value = values.get(field, "").strip()
                if value:
                    setattr(existing, field, value)
            return "updated"
        else:
            # 创建新单词
            word = Word(
                deck_id=deck.id,
                w=word_text,
                c=values.get("c") or "",
                zh=values.get("zh") or "",
                en=values.get("en") or "",
                us=values.get("us") or "",
                core=values.get("core") or "",
                ex=values.get("ex") or "",
                exz=values.get("exz") or "",
                normalized_word=normalized,
            )
            word.card = Card(due=datetime.now(timezone.utc).replace(tzinfo=None))
            self.session.add(word)
            return "inserted"
