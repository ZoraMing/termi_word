# Termi Word 架构、操作逻辑与数据逻辑重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Termi Word 的 TUI 操作逻辑、数据访问逻辑、业务服务和渲染职责拆分成可独立理解、可模块测试、可渐进替换的结构。

**Architecture:** 保持当前 Textual + SQLAlchemy + SQLite + FSRS 技术栈不变，先提取纯逻辑和边界对象，再让 Screen 只负责输入事件与渲染状态。数据层从单一 `AppRepository` 拆为更小的仓储/查询/迁移职责，服务层返回结构化结果，UI 层再决定展示文案。

**Tech Stack:** Python, Textual, SQLAlchemy, SQLite, py-fsrs, unittest/pytest-compatible tests.

**Execution Policy:** 本计划不包含 `git commit`、分支、推送步骤。实现时除非用户明确要求，否则不要执行提交。涉及数据库结构迁移或批量数据修改前必须按 AGENTS 危险操作格式单独确认。

---

## 现状问题摘要

### 架构问题

- `database/repositories.py` 中 `AppRepository` 同时负责设置热迁移、词本查询、单词 upsert、统计、会话读取，职责过宽。
- `screens/*` 中多处重复 `apply_dynamic_layout`，导致 `word_detail.py`、`words.py` 等页面开始出现行为漂移。
- `services/*` 多数服务直接返回中文用户文案，业务结果与 UI 展示耦合。
- `SchedulerService.review()` 写入 `data/debug_timezone.log`，纯调度逻辑混入本地调试副作用。

### 操作逻辑问题

- 键盘操作是正确方向，但 `Enter`、`Space`、`f`、`Esc` 在不同页面语义不稳定。
- `t` 挂起、词书启用后自动同步、字段映射循环切换等高影响操作缺少确认或撤销。
- 词表详情锁定、设置编辑、拼写答案等模式状态主要靠单行消息栏提示，可见性不足。
- `Input:focus` 去除了边框和背景，焦点状态对键盘用户不够明确。

### 数据逻辑问题

- `StudySession.remaining_card_ids` 以 JSON 文本存储并在服务中反复 `json.loads/json.dumps`，错误被吞掉。
- 设置表迁移分散在 `database/engine.py` 和 `AppRepository.get_settings()` 中。
- 导入服务既解析 CSV、读取设置映射、写数据库，又格式化中文结果。
- 渲染路径中存在同步数据库访问和全量搜索排序，TUI 响应性会随词量下降。

---

## 目标边界

### 本轮重构目标

1. 保持用户可见功能不变。
2. 把 UI 事件处理、领域决策、数据库读写、展示文案分开。
3. 给调度、会话队列、拼写判定、CSV 解析、键盘状态机提供模块测试入口。
4. 降低后续改动 Screen 时引发跨页面行为漂移的风险。

### 非目标

- 不更换 Textual。
- 不引入 Alembic 或复杂迁移框架；先做轻量迁移模块集中化。
- 不重写 FSRS 算法。
- 不改变现有数据文件位置。
- 不在本计划中要求提交 git。

---

## 目标文件结构

### 新增文件

- `ui/layout.py`: 统一 frame/content/message/footer 高度与宽度计算。
- `ui/keyboard.py`: 定义按键语义、页面模式和高影响动作确认策略。
- `ui/messages.py`: 将业务结果映射为用户可见消息。
- `domain/results.py`: 定义结构化结果对象，例如 `StudyActionResult`、`ImportResult`、`SpellingResult`。
- `domain/session_queue.py`: 封装 `remaining_card_ids` 的序列化、反序列化和移除逻辑。
- `database/migrations.py`: 集中轻量 SQLite 表结构补丁。
- `database/settings_repository.py`: 设置读取与保存。
- `database/deck_repository.py`: 词本读取、创建、激活。
- `database/word_repository.py`: 单词查询、搜索、upsert。
- `database/study_repository.py`: 卡片队列、复习日志、学习会话。
- `database/stats_repository.py`: 今日统计、活动日期、连续打卡。
- `tests/helpers.py`: 创建临时 SQLite session factory 和测试数据。
- `tests/test_session_queue.py`: 会话队列纯逻辑测试。
- `tests/test_scheduler_service.py`: 调度服务副作用和时间归一化测试。
- `tests/test_import_service.py`: CSV 解析、字段映射、导入结果测试。
- `tests/test_keyboard_policy.py`: 键盘语义和确认策略测试。
- `tests/test_repositories.py`: 仓储边界和轻量集成测试。

### 修改文件

- `app.py`: 注入更清晰的服务对象，统一全局搜索和 Esc 行为。
- `ui.py`: 保留显示宽度/截断/换行工具，逐步迁移布局函数到 `ui/layout.py`。
- `styles/app.tcss`: 增加 focus 可见样式和语义色 token 注释。
- `database/engine.py`: 调用 `database/migrations.py`。
- `database/repositories.py`: 过渡期保留兼容 facade，逐步委托到小仓储。
- `services/study_service.py`: 返回结构化结果，使用 `domain/session_queue.py`。
- `services/scheduler_service.py`: 移除调试文件写入，注入 clock。
- `services/import_service.py`: 拆分 CSV 解析、导入执行、结果格式化。
- `services/spelling_service.py`: 返回 `SpellingResult`。
- `screens/today.py`, `screens/review.py`, `screens/words.py`, `screens/settings.py`, `screens/deck_config.py`, `screens/calendar.py`, `screens/spelling.py`, `screens/word_detail.py`: 使用共享布局和键盘策略，减少本地状态机重复。

---

## Task 1: 建立领域结果对象

**Files:**
- Create: `domain/results.py`
- Modify: `services/import_service.py`
- Modify: `services/spelling_service.py`
- Test: `tests/test_import_service.py`
- Test: `tests/test_spelling_service.py`

- [ ] **Step 1: 创建结果对象**

```python
"""领域服务返回结果对象。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportResult:
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
    word_id: int
    expected: str
    typed: str
    is_correct: bool
    hint_used_count: int
```

- [ ] **Step 2: 为导入结果格式化写测试**

```python
from termi_word.domain.results import ImportResult
from termi_word.ui.messages import format_import_result


def test_format_import_result_insert_update_skip():
    result = ImportResult(imported=2, updated=3, skipped=1)
    assert format_import_result(result) == "已导入 2 个单词，更新 3 个单词，跳过 1 行"


def test_format_import_result_missing_fields():
    result = ImportResult(missing_fields=("w", "zh"))
    assert format_import_result(result) == "同步失败！词表字段缺失：w, zh。请先绑定字段后再试。"
```

- [ ] **Step 3: 创建 UI 消息格式化模块**

```python
"""将结构化业务结果转换为用户可见中文文案。"""
from __future__ import annotations

from termi_word.domain.results import ImportResult, SpellingResult


def format_import_result(result: ImportResult) -> str:
    if result.source_missing:
        return f"找不到词表：{result.source_missing}"
    if result.missing_fields:
        return f"同步失败！词表字段缺失：{', '.join(result.missing_fields)}。请先绑定字段后再试。"

    parts: list[str] = []
    if result.imported:
        parts.append(f"已导入 {result.imported} 个单词")
    if result.updated:
        parts.append(f"更新 {result.updated} 个单词")
    if result.skipped and not parts:
        return "词表已就绪"
    if result.skipped:
        parts.append(f"跳过 {result.skipped} 行")
    return "，".join(parts) if parts else "没有可导入的单词"


def format_spelling_result(result: SpellingResult) -> str:
    if result.is_correct:
        return "太棒了，拼写正确！"
    return f"拼写错误。正确拼写应为: {result.expected}"
```

- [ ] **Step 4: 修改服务层返回结构化结果**

`ImportService.import_rows()` 返回 `ImportResult`，不再返回中文字符串。`SpellingService.submit()` 返回 `SpellingResult`，不再只返回 bool。

- [ ] **Step 5: 修改 Screen 使用 `ui.messages` 格式化文案**

`screens/deck_config.py` 和 `screens/spelling.py` 只负责调用格式化函数并更新 `last_msg`。

- [ ] **Step 6: 验证**

Run only when user approves test execution:

```bash
python -m pytest tests/test_import_service.py tests/test_spelling_service.py -v
```

Expected: 新增测试通过，现有导入与拼写行为不变。

---

## Task 2: 提取学习会话队列纯逻辑

**Files:**
- Create: `domain/session_queue.py`
- Modify: `services/study_service.py`
- Test: `tests/test_session_queue.py`

- [ ] **Step 1: 创建会话队列值对象**

```python
"""学习会话队列的纯逻辑。"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionQueueIds:
    ids: tuple[int, ...]

    @classmethod
    def from_json(cls, raw: str | None) -> "SessionQueueIds":
        if not raw:
            return cls(())
        values = json.loads(raw)
        if not isinstance(values, list):
            return cls(())
        return cls(tuple(int(value) for value in values))

    def to_json(self) -> str:
        return json.dumps(list(self.ids), ensure_ascii=False)

    def remove(self, card_id: int) -> "SessionQueueIds":
        return SessionQueueIds(tuple(value for value in self.ids if value != card_id))

    @property
    def is_empty(self) -> bool:
        return not self.ids
```

- [ ] **Step 2: 写队列测试**

```python
from termi_word.domain.session_queue import SessionQueueIds


def test_session_queue_round_trip():
    queue = SessionQueueIds.from_json("[3, 1, 2]")
    assert queue.ids == (3, 1, 2)
    assert queue.to_json() == "[3, 1, 2]"


def test_session_queue_remove_preserves_order():
    queue = SessionQueueIds((3, 1, 2)).remove(1)
    assert queue.ids == (3, 2)
    assert not queue.is_empty


def test_session_queue_empty_inputs():
    assert SessionQueueIds.from_json(None).ids == ()
    assert SessionQueueIds.from_json("").ids == ()
```

- [ ] **Step 3: 替换 `StudyService` 中的 JSON 操作**

在 `build_today_queue()`、`rate_card()`、`suspend_word()` 中使用 `SessionQueueIds`。不要吞掉 JSON 异常；如果历史数据损坏，返回空队列并记录结构化错误，UI 层显示“会话队列已重置”。

- [ ] **Step 4: 验证**

Run only when user approves test execution:

```bash
python -m pytest tests/test_session_queue.py -v
```

Expected: 纯逻辑测试通过。

---

## Task 3: 拆分仓储职责并保留兼容 facade

**Files:**
- Create: `database/settings_repository.py`
- Create: `database/deck_repository.py`
- Create: `database/word_repository.py`
- Create: `database/study_repository.py`
- Create: `database/stats_repository.py`
- Modify: `database/repositories.py`
- Test: `tests/test_repositories.py`

- [ ] **Step 1: 提取设置仓储**

`SettingsRepository` 只提供：

```python
class SettingsRepository:
    def __init__(self, session):
        self.session = session

    def get(self):
        ...

    def save(self, setting) -> None:
        self.session.flush()
```

迁移逻辑不要放在这里，迁移由 Task 4 处理。

- [ ] **Step 2: 提取词本仓储**

`DeckRepository` 只提供：

```python
class DeckRepository:
    def __init__(self, session, settings_repository):
        self.session = session
        self.settings_repository = settings_repository

    def get_or_create(self, name: str, description: str = ""):
        ...

    def active(self):
        ...
```

- [ ] **Step 3: 提取单词仓储**

`WordRepository` 负责：

- `word_count(deck_id: int | None = None) -> int`
- `list_with_cards(deck_id: int) -> list[Word]`
- `list_all_with_cards() -> list[Word]`
- `upsert(deck: Deck, values: dict[str, str]) -> str`
- `get_by_id(word_id: int) -> Word | None`

- [ ] **Step 4: 提取学习仓储**

`StudyRepository` 负责：

- `due_cards(deck_id: int, limit: int | None) -> list[Card]`
- `new_cards(deck_id: int, limit: int) -> list[Card]`
- `cards_by_ids(card_ids: Iterable[int]) -> list[Card]`
- `open_session(deck_id: int) -> StudySession | None`
- `add_review_log(log: ReviewLog) -> None`

- [ ] **Step 5: 提取统计仓储**

`StatsRepository` 负责：

- `today_review_count() -> int`
- `today_new_and_review_counts() -> tuple[int, int]`
- `today_spelling_count() -> int`
- `activity_dates() -> set[date]`
- `streak_days() -> int`

- [ ] **Step 6: 保留 `AppRepository` facade**

`AppRepository` 暂时保留原方法名，内部委托到新仓储。这样 Screen 和 Service 可以分批迁移，避免一次性大改。

- [ ] **Step 7: 验证**

Run only when user approves test execution:

```bash
python -m pytest tests/test_repositories.py -v
```

Expected: 仓储方法覆盖 active deck、word upsert、due/new cards、today stats。

---

## Task 4: 集中数据库轻量迁移

**Files:**
- Create: `database/migrations.py`
- Modify: `database/engine.py`
- Modify: `database/repositories.py`
- Test: `tests/test_migrations.py`

- [ ] **Step 1: 创建迁移模块**

```python
"""SQLite 轻量迁移。"""
from __future__ import annotations

from sqlalchemy.engine import Engine


SETTINGS_COLUMNS = {
    "search_shortcut": "ALTER TABLE settings ADD COLUMN search_shortcut VARCHAR(30) DEFAULT 'ctrl+slash'",
    "panel_max_width": "ALTER TABLE settings ADD COLUMN panel_max_width INTEGER DEFAULT 120",
    "panel_min_height": "ALTER TABLE settings ADD COLUMN panel_min_height INTEGER DEFAULT 6",
    "panel_max_height": "ALTER TABLE settings ADD COLUMN panel_max_height INTEGER DEFAULT 16",
    "csv_column_mapping": "ALTER TABLE settings ADD COLUMN csv_column_mapping TEXT",
}


def apply_lightweight_migrations(engine: Engine) -> None:
    with engine.begin() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info(settings)")
        existing = {row[1] for row in result}
        for column, ddl in SETTINGS_COLUMNS.items():
            if column not in existing:
                conn.exec_driver_sql(ddl)
```

- [ ] **Step 2: `engine.py` 调用迁移模块**

`init_database()` 在 `Base.metadata.create_all(engine)` 后调用 `apply_lightweight_migrations(engine)`。

- [ ] **Step 3: 删除 `AppRepository.get_settings()` 中的热迁移**

`get_settings()` 只负责获取或创建设置行，不再执行 `ALTER TABLE`。

- [ ] **Step 4: 验证**

Run only when user approves test execution:

```bash
python -m pytest tests/test_migrations.py -v
```

Expected: 老 settings 表缺列时能补齐；重复执行迁移不会报错。

---

## Task 5: 清理 SchedulerService 副作用并注入 clock

**Files:**
- Modify: `services/scheduler_service.py`
- Modify: `tests/test_scheduler.py`
- Test: `tests/test_scheduler_service.py`

- [ ] **Step 1: 调整构造函数**

```python
from collections.abc import Callable
from datetime import datetime, timezone


def default_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SchedulerService:
    def __init__(self, now: Callable[[], datetime] = default_utc_now) -> None:
        self.scheduler = Scheduler(enable_fuzzing=False)
        self.now = now
```

- [ ] **Step 2: 移除 `data/debug_timezone.log` 写入**

删除 `review()` 中所有 `os.makedirs`、`open("data/debug_timezone.log"...` 和 `traceback` 写文件逻辑。异常应直接抛出，由调用层决定展示。

- [ ] **Step 3: 使用注入时间**

所有 `datetime.now(timezone.utc)` 替换为 `self.now()`，存回 SQLite 时仍去掉 tzinfo。

- [ ] **Step 4: 增加无文件副作用测试**

```python
from pathlib import Path
from datetime import datetime, timezone

from termi_word.database.models import Card
from termi_word.services.scheduler_service import SchedulerService


def test_scheduler_review_does_not_write_debug_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = SchedulerService(now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    card = Card(id=1, state=0, due=datetime(2026, 1, 1), last_review=None, reps=0, lapses=0)

    service.review(card, 3)

    assert not Path("data/debug_timezone.log").exists()
```

- [ ] **Step 5: 验证**

Run only when user approves test execution:

```bash
python -m pytest tests/test_scheduler.py tests/test_scheduler_service.py -v
```

Expected: 调度测试通过，不再生成 debug 文件。

---

## Task 6: 建立共享布局层

**Files:**
- Create: `ui/layout.py`
- Modify: `ui.py`
- Modify: `screens/today.py`
- Modify: `screens/review.py`
- Modify: `screens/words.py`
- Modify: `screens/settings.py`
- Modify: `screens/calendar.py`
- Modify: `screens/deck_config.py`
- Modify: `screens/spelling.py`
- Modify: `screens/word_detail.py`
- Test: `tests/test_layout.py`

- [ ] **Step 1: 创建布局结果对象**

```python
"""Textual Frame 布局计算。"""
from __future__ import annotations

from dataclasses import dataclass

from termi_word.ui import footer_height, panel_height, panel_width


@dataclass(frozen=True)
class FrameLayout:
    frame_height: int
    frame_width: int
    content_height: int
    content_width: int
    footer_rows: int
    message_rows: int


def compute_frame_layout(
    terminal_width: int,
    terminal_height: int,
    panel_min_height: int,
    panel_max_height: int,
    panel_max_width: int,
    footer_text: str,
    has_input: bool = False,
    message_rows: int = 1,
) -> FrameLayout:
    frame_height = panel_height(terminal_height, panel_min_height, panel_max_height)
    frame_width = panel_width(terminal_width, panel_max_width)
    content_width = max(1, frame_width - 2)
    footer_rows = footer_height(footer_text, content_width)
    input_rows = 1 if has_input else 0
    content_height = max(3, frame_height - 2 - input_rows - message_rows - footer_rows)
    return FrameLayout(frame_height, frame_width, content_height, content_width, footer_rows, message_rows)
```

- [ ] **Step 2: 写布局测试**

```python
from termi_word.ui.layout import compute_frame_layout


def test_compute_frame_layout_with_input_and_wrapped_footer():
    layout = compute_frame_layout(
        terminal_width=40,
        terminal_height=12,
        panel_min_height=6,
        panel_max_height=16,
        panel_max_width=68,
        footer_text="Enter 提交   Tab 提示   Space 答案   s 跳过   Esc 返回",
        has_input=True,
    )
    assert layout.frame_width <= 68
    assert layout.content_width == layout.frame_width - 2
    assert layout.content_height >= 3
```

- [ ] **Step 3: Screen 迁移到共享布局**

每个 Screen 的 `apply_dynamic_layout` 只保留：

1. 获取 setting。
2. 调用 `compute_frame_layout(...)`。
3. 应用 `.frame-container`、`#content-area`、`#footer-area`、`#message-area` 样式。

- [ ] **Step 4: 增加 resize 入口**

为每个 Screen 增加 `on_resize()`，只调用当前页面的 render 方法。后续可以提取 Screen 基类。

- [ ] **Step 5: 修正 `word_detail.py` 高度**

`text_panel()` 的 `height` 参数传入 `content_height` 或改为明确接收 body 高度，不再混用 frame 高度。

- [ ] **Step 6: 验证**

Run only when user approves test execution:

```bash
python -m pytest tests/test_layout.py -v
```

Expected: 布局计算纯逻辑通过；手动运行 TUI 后缩放终端不会保持旧布局。

---

## Task 7: 建立键盘策略与确认机制

**Files:**
- Create: `ui/keyboard.py`
- Modify: `app.py`
- Modify: `screens/review.py`
- Modify: `screens/words.py`
- Modify: `screens/settings.py`
- Modify: `screens/deck_config.py`
- Modify: `screens/spelling.py`
- Modify: `services/ui_config_service.py`
- Test: `tests/test_keyboard_policy.py`

- [ ] **Step 1: 定义键盘语义**

```python
"""键盘语义与高影响操作策略。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KeyIntent(str, Enum):
    CONFIRM = "confirm"
    TOGGLE_PREVIEW = "toggle_preview"
    BACK = "back"
    HELP = "help"
    GLOBAL_SEARCH = "global_search"
    DANGEROUS_ACTION = "dangerous_action"


@dataclass(frozen=True)
class PendingConfirmation:
    action: str
    prompt: str
    confirm_key: str = "y"
    cancel_key: str = "escape"


HIGH_IMPACT_ACTIONS = {
    "suspend_word": "再次按 y 挂起该单词，Esc 取消",
    "sync_deck": "再次按 y 同步当前词书，Esc 取消",
    "change_mapping": "再次按 y 修改字段映射，Esc 取消",
}
```

- [ ] **Step 2: 写策略测试**

```python
from termi_word.ui.keyboard import HIGH_IMPACT_ACTIONS, PendingConfirmation


def test_high_impact_actions_have_prompts():
    assert "suspend_word" in HIGH_IMPACT_ACTIONS
    assert "Esc 取消" in HIGH_IMPACT_ACTIONS["suspend_word"]


def test_pending_confirmation_defaults():
    pending = PendingConfirmation(action="sync_deck", prompt="confirm")
    assert pending.confirm_key == "y"
    assert pending.cancel_key == "escape"
```

- [ ] **Step 3: ReviewScreen 挂起增加确认或 undo**

推荐最小改法：`t` 第一次只设置 pending confirmation 并提示；`y` 才执行 `suspend_word()`；`Esc` 取消 pending。

- [ ] **Step 4: DeckConfig 高影响操作增加确认**

词书启用并同步、字段映射切换都进入 pending confirmation。低风险展示开关可以继续单键切换。

- [ ] **Step 5: 增加 `?` 帮助层**

最小实现：每个 Screen 响应 `?`，在 `message-area` 或临时 help panel 显示当前页面快捷键。不要引入复杂 modal。

- [ ] **Step 6: 统一 footer 文案**

在 `services/ui_config_service.py` 中把 footer 调整为：

- `Enter`: 主确认。
- `Space`: 预览/翻卡/切换。
- `Esc`: 退出当前模式或返回。
- `?`: 显示帮助。
- 高影响动作标注“需确认”。

- [ ] **Step 7: 验证**

Run only when user approves test execution:

```bash
python -m pytest tests/test_keyboard_policy.py -v
```

Expected: 键盘策略测试通过。手动验证 `t`、同步词书、字段映射不会单键立即执行。

---

## Task 8: 优化搜索与渲染性能边界

**Files:**
- Modify: `screens/words.py`
- Modify: `database/word_repository.py`
- Test: `tests/test_word_search.py`

- [ ] **Step 1: 把搜索评分移到纯函数**

```python
def score_word_search(word_text: str, zh: str, search_text: str, query: str) -> int:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return 1
    word_lower = word_text.lower()
    if word_lower == normalized_query:
        return 10000
    if word_lower.startswith(normalized_query):
        return 8000 + len(normalized_query)
    zh_lower = zh.lower()
    if normalized_query in zh_lower:
        if zh_lower.startswith(normalized_query) or zh_lower == normalized_query:
            return 7500 + len(normalized_query)
        return 6000 - zh_lower.find(normalized_query)
    pos = search_text.find(normalized_query)
    if pos >= 0:
        return 5000 - pos + len(normalized_query) * 20
    return 0
```

- [ ] **Step 2: 写搜索评分测试**

```python
from termi_word.screens.words import score_word_search


def test_score_word_exact_match_wins():
    assert score_word_search("apple", "苹果", "apple 苹果", "apple") == 10000


def test_score_word_zh_match():
    assert score_word_search("apple", "苹果", "apple 苹果", "苹") > 0


def test_score_word_no_match():
    assert score_word_search("apple", "苹果", "apple 苹果", "banana") == 0
```

- [ ] **Step 3: 限制每次渲染的排序范围**

保持 `entries` 缓存，但对空 query 不做排序；对非空 query 保留前 N 个结果用于渲染。N 初始设为 200，避免全量词库每次输入都完整渲染。

- [ ] **Step 4: 验证**

Run only when user approves test execution:

```bash
python -m pytest tests/test_word_search.py -v
```

Expected: 搜索评分纯逻辑通过；词表页输入响应不依赖数据库重新查询。

---

## Task 9: 收敛主题与焦点样式

**Files:**
- Modify: `styles/app.tcss`
- Modify: `ui/messages.py`
- Test: manual TUI verification

- [ ] **Step 1: 增加语义色注释块**

TCSS 目前不一定支持完整 CSS custom properties。先用注释建立 token 表，避免色值语义漂移：

```css
/* Theme tokens
   text: #d5d9e0
   muted: #9CA3AF
   border: #6B7280
   accent: #F59E0B
   success: #4ADE80
   error: #F87171
   focus-bg: #1f2937
*/
```

- [ ] **Step 2: 给 Input focus 可见状态**

```css
Input:focus {
    border: none;
    background: #1f2937;
    color: #FBBF24;
}
```

- [ ] **Step 3: 保持极简但增加模式可见性**

各 Screen 标题加入模式标签，不靠颜色单独表达状态，例如：

- `Words / Search`
- `Words / Browse`
- `Words / Detail Locked`
- `Settings / Editing`
- `Review / Front`
- `Review / Revealed`

- [ ] **Step 4: 验证**

Manual only unless user asks for automated UI tests:

```bash
python -m termi_word
```

Expected: 输入焦点肉眼可见；锁定详情、编辑模式、翻卡状态在标题或首行可见。

---

## Task 10: 最终清理与回归检查

**Files:**
- Review all modified files above.
- Test: affected tests only first, then full suite if user approves.

- [ ] **Step 1: 删除重复布局实现**

确认以下文件不再保留完整重复 `apply_dynamic_layout` 计算逻辑：

- `screens/today.py`
- `screens/review.py`
- `screens/words.py`
- `screens/settings.py`
- `screens/calendar.py`
- `screens/deck_config.py`
- `screens/spelling.py`
- `screens/word_detail.py`

- [ ] **Step 2: 搜索异常吞噬**

Run only when user approves command execution:

```bash
rg -n "except Exception|pass" services database screens
```

Expected: 只剩有明确注释和恢复策略的位置。

- [ ] **Step 3: 搜索服务层中文文案**

Run only when user approves command execution:

```bash
rg -n "已|错误|失败|成功|请输入|找不到|词表字段缺失" services database
```

Expected: 服务/数据库层不再返回 UI 文案；文案集中在 `ui/messages.py` 或 Screen。

- [ ] **Step 4: 运行模块测试**

Run only when user approves test execution:

```bash
python -m pytest tests/test_session_queue.py tests/test_scheduler_service.py tests/test_import_service.py tests/test_keyboard_policy.py tests/test_layout.py tests/test_word_search.py -v
```

Expected: 新模块测试全部通过。

- [ ] **Step 5: 运行现有回归测试**

Run only when user approves test execution:

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected: 现有调度测试仍通过。

---

## 实施顺序建议

1. 先做 Task 2 和 Task 5：纯逻辑、低耦合，收益高，风险低。
2. 再做 Task 1：统一服务返回结构化结果，降低 UI/业务耦合。
3. 再做 Task 3 和 Task 4：拆数据层和迁移层，保持 `AppRepository` facade 降低风险。
4. 再做 Task 6 和 Task 7：统一布局和键盘策略，改善用户操作逻辑。
5. 最后做 Task 8、Task 9、Task 10：性能、主题、回归清理。

---

## 风险控制

- 每个任务都应保持可运行状态，不做跨 10 个文件的大爆炸式重写。
- `AppRepository` 先作为兼容 facade 保留，避免 Screen 和 Service 同时大面积改。
- 数据库迁移集中后，先用临时 SQLite 测试验证，不直接操作用户真实 `data/termi_word.sqlite3`。
- 高影响键盘动作的确认机制先做最小实现，不引入复杂 modal。
- 测试优先覆盖纯逻辑和仓储边界，TUI 手动验证作为补充。

---

## 自查清单

- [x] 覆盖架构职责分离。
- [x] 覆盖键盘操作逻辑。
- [x] 覆盖数据逻辑和迁移边界。
- [x] 覆盖服务返回结构化结果。
- [x] 覆盖模块测试入口。
- [x] 避免引入新框架和过度设计。
- [x] 不包含 git commit / push / branch 步骤。
