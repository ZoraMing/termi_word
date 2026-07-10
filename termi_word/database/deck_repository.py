"""词本数据存取仓储。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from termi_word.database.models import Deck
from termi_word.database.settings_repository import SettingsRepository


class DeckRepository:
    """负责词本的查询、创建与激活逻辑"""

    def __init__(self, session: Session, settings_repository: SettingsRepository) -> None:
        self.session = session
        self.settings_repository = settings_repository

    def get_or_create(self, name: str, description: str = "") -> Deck:
        """根据名称获取或创建词本。如果是第一个词本，自动设为活跃。"""
        deck = self.session.execute(select(Deck).where(Deck.name == name)).scalars().first()
        if deck is not None:
            return deck
        deck = Deck(name=name, description=description)
        self.session.add(deck)
        self.session.flush()

        setting = self.settings_repository.get()
        if setting.active_deck_id is None:
            setting.active_deck_id = deck.id
        return deck

    def active(self) -> Deck | None:
        """获取当前活跃的词本。如果未指定但存在词本，取第一个。"""
        setting = self.settings_repository.get()
        if setting.active_deck_id:
            deck = self.session.get(Deck, setting.active_deck_id)
            if deck is not None:
                return deck
        deck = self.session.execute(select(Deck).order_by(Deck.id)).scalars().first()
        if deck is not None:
            setting.active_deck_id = deck.id
        return deck
