from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import or_
from sqlalchemy.orm import Session, sessionmaker

from termi_word.database.models import Word
from termi_word.database.repositories import AppRepository


@dataclass(frozen=True)
class SearchEntry:
    word_id: int
    title: str
    detail: str
    searchable: str
    lines: tuple[str, ...]


class SearchService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def search(self, deck_name: str, query: str = "", limit: int = 100) -> list[SearchEntry]:
        with self.session_factory() as session:
            repo = AppRepository(session)
            deck = repo.active_deck(deck_name)
            if deck is None:
                return []
            if not query:
                words = repo.list_words_limited(deck.id, limit)
                return [self.to_entry(w) for w in words]
            # Database-level LIKE filter, then Python fuzzy ranking
            candidates = repo.search_words(deck.id, query, limit * 3)
            entries = [self.to_entry(w) for w in candidates]
            scored = [(self.fuzzy_score(e, query), e) for e in entries]
            return [e for score, e in sorted(scored, key=lambda x: x[0], reverse=True) if score > 0][:limit]

    def word_detail(self, word_id: int) -> Word | None:
        with self.session_factory() as session:
            return AppRepository(session).word_by_id(word_id)

    def fuzzy_score(self, entry: SearchEntry, query: str) -> float:
        title = entry.title.lower()
        text = entry.searchable
        if title == query:
            return 10000.0
        if title.startswith(query):
            return 8000.0 + len(query)
        ratio = SequenceMatcher(None, query, title).ratio()
        if ratio > 0.6:
            return 6000.0 * ratio
        position = text.find(query)
        if position >= 0:
            return 5000.0 - position + len(query) * 20
        return 0.0

    def to_entry(self, word: Word) -> SearchEntry:
        meaning = word.core or word.zh or word.en
        searchable = " ".join([word.w, word.c, word.zh, word.en, word.core]).lower()
        lines = tuple(
            line
            for line in [
                f"单词      {word.w}  {word.us or ''}  [{word.c or '-'}]",
                f"核心释义  {word.core}" if word.core else "",
                f"中文释义  {word.zh}" if word.zh else "",
                f"英文定义  {word.en}" if word.en else "",
                f"例句      {word.ex}" if word.ex else "",
                f"翻译      {word.exz}" if word.exz else "",
            ]
            if line
        )
        return SearchEntry(word.id, word.w, meaning, searchable, lines)
