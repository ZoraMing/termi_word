"""领域服务返回结果对象。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportResult:
    """导入词表结果封装"""
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    missing_fields: tuple[str, ...] = ()
    source_missing: str | None = None

    @property
    def ok(self) -> bool:
        return self.source_missing is None and not self.missing_fields


@dataclass(frozen=True)
class SpellingResult:
    """拼写检测结果封装"""
    word_id: int
    expected: str
    typed: str
    is_correct: bool
    hint_used_count: int


@dataclass(frozen=True)
class StudyActionResult:
    """背词评分等动作结果封装"""
    card_id: int
    rating: int
    scheduled_days: int
    msg: str
