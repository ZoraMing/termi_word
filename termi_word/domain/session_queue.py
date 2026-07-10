"""学习会话队列的纯逻辑。"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionQueueIds:
    """背词会话剩余卡片ID队列封装"""
    ids: tuple[int, ...]

    @classmethod
    def from_json(cls, raw: str | None) -> "SessionQueueIds":
        """从 JSON 字符串反序列化，容错性强"""
        if not raw:
            return cls(())
        try:
            values = json.loads(raw)
            if not isinstance(values, list):
                return cls(())
            return cls(tuple(int(value) for value in values))
        except Exception:
            # 容错处理：历史数据损坏时返回空队列
            return cls(())

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(list(self.ids), ensure_ascii=False)

    def remove(self, card_id: int) -> "SessionQueueIds":
        """从中安全移除指定卡片ID，返回新队列对象"""
        return SessionQueueIds(tuple(value for value in self.ids if value != card_id))

    @property
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return not self.ids
