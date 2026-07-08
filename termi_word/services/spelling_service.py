from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from termi_word.database.models import Word
from termi_word.database.repositories import AppRepository


@dataclass(frozen=True)
class SpellingResult:
    ok: bool
    answer: str
    message: str


class SpellingService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def candidates(self, deck_name: str, limit: int) -> list[Word]:
        with self.session_factory() as session:
            return AppRepository(session).spelling_candidates(deck_name, limit)

    def submit(self, word_id: int, answer: str, hint_count: int) -> SpellingResult:
        with self.session_factory() as session:
            repo = AppRepository(session)
            word = repo.word_by_id(word_id)
            if word is None:
                return SpellingResult(False, "", "单词不存在")
            normalized_input = answer.strip().lower()
            normalized_answer = word.w.strip().lower()
            ok = normalized_input == normalized_answer
            repo.add_spelling_log(word.id, answer, ok, hint_count)
            session.commit()
            return SpellingResult(ok, word.w, "拼写正确" if ok else f"拼写错误：{word.w}")
