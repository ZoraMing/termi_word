from __future__ import annotations

from functools import partial

from textual.command import Hit, Hits, Provider


class WordSearchProvider(Provider):
    async def startup(self) -> None:
        config = self.app.config_service.load()
        self.deck_name = config.active_deck

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        entries = self.app.search_service.search(self.deck_name, query, 50)
        for entry in entries:
            score = matcher.match(entry.searchable)
            if score <= 0:
                continue
            yield Hit(
                score,
                matcher.highlight(entry.title),
                partial(self.app.open_word_detail, entry.word_id),
                text=entry.searchable,
                help=entry.detail or "查看单词详情",
            )
