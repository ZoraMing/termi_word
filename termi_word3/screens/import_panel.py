"""导入词表的预览与选择屏幕"""
from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static

from termi_word3.services.import_service import ImportRow
from termi_word3.domain.results import ImportResult
from termi_word3.ui import clamp_scroll_offset, panel_body_height, panel_height, panel_width, scroll_window, text_panel, truncate_display
from termi_word3.ui.messages import format_import_result


class ImportScreen(Screen):
    """导入词表的预览与选择屏幕"""

    BINDINGS = [("escape", "back", "返回")]

    def __init__(self, deck_name: str) -> None:
        super().__init__()
        self.deck_name = deck_name
        self.source_path = None
        self.rows: list[ImportRow] = []
        self.missing_fields: tuple[str, ...] = ()
        self.skip_rows: set[int] = set()
        self.selected = 0
        self.row_offset = 0
        self.message = ""
        self._import_worker = None
        self._is_importing = False

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.reload_source()
        self.render_panel()

    def reload_source(self) -> None:
        self.source_path, self.rows, self.missing_fields = self.app.import_service.read_source_rows(self.deck_name)
        self.selected = 0
        self.row_offset = 0

    def on_key(self, event: Key) -> None:
        if self.missing_fields:
            if event.key == "escape":
                event.stop()
                self.action_back()
            return

        if event.key == "up":
            event.stop()
            self.move(-1)
        elif event.key == "down":
            event.stop()
            self.move(1)
        elif event.key == "space":
            event.stop()
            self.toggle_skip()
        elif event.key in {"enter", "return"}:
            event.stop()
            self.import_rows()

    def move(self, delta: int) -> None:
        if not self.rows:
            return
        self.selected = max(0, min(len(self.rows) - 1, self.selected + delta))
        visible_count = self.visible_row_count()
        if self.selected < self.row_offset:
            self.row_offset = self.selected
        elif self.selected >= self.row_offset + visible_count:
            self.row_offset = self.selected - visible_count + 1
        self.render_panel()

    def toggle_skip(self) -> None:
        if not self.rows:
            return
        row_number = self.rows[self.selected].row_number
        if row_number in self.skip_rows:
            self.skip_rows.remove(row_number)
            self.message = f"已恢复第 {row_number} 行"
        else:
            self.skip_rows.add(row_number)
            self.message = f"已跳过第 {row_number} 行"
        self.render_panel()

    def import_rows(self) -> None:
        if self._is_importing:
            return
        self._is_importing = True
        self.message = "正在导入词表..."
        self.render_panel()
        self._import_worker = self.run_worker(self._import_rows_async(), exclusive=True)
        self._register_worker(self._import_worker)

    async def _import_rows_async(self) -> None:
        """在 worker 中执行导入，避免阻塞 UI 主线程。"""
        try:
            skip_rows = set(self.skip_rows)
            csv_to_use, rows, missing = await asyncio.to_thread(
                self.app.import_service.read_source_rows,
                self.deck_name,
            )
            if not csv_to_use.exists():
                result = ImportResult(source_missing=str(csv_to_use))
            elif missing:
                result = ImportResult(missing_fields=missing)
            else:
                result = await self._import_rows_in_batches(rows, skip_rows)
            self.message = format_import_result(result)
        except asyncio.CancelledError:
            self.message = "导入已取消。"
            raise
        except Exception as exc:
            self.message = f"导入失败（系统异常）: {exc}"
        finally:
            self._is_importing = False
            self._unregister_worker(self._import_worker)
            self._import_worker = None
            if getattr(self, "is_mounted", True):
                self.render_panel()

    async def _import_rows_in_batches(self, rows: list[ImportRow], skip_rows: set[int]):
        """按批写入数据库，让取消最多等待当前批次完成。"""
        imported = 0
        updated = 0
        skipped = 0
        batch_size = self.app.import_service.BATCH_SIZE
        for start in range(0, len(rows), batch_size):
            await asyncio.sleep(0)
            batch = rows[start:start + batch_size]
            partial = await asyncio.to_thread(
                self.app.import_service.import_prepared_rows,
                self.deck_name,
                batch,
                skip_rows,
            )
            imported += partial.imported
            updated += partial.updated
            skipped += partial.skipped

        return ImportResult(imported=imported, updated=updated, skipped=skipped)

    def visible_row_count(self) -> int:
        return max(1, panel_body_height(self.panel_height()) - 4)

    def row_lines(self) -> list[str]:
        lines: list[str] = []
        width = self.content_width()
        for row in self.rows:
            marker = "> " if row.row_number == self.current_row_number else "  "
            state = "[跳过]" if row.row_number in self.skip_rows else "[导入]"
            preview = "  ".join(
                part
                for part in [
                    f"{row.row_number:>4}",
                    state,
                    row.values.get("w", ""),
                    row.values.get("c", ""),
                    row.values.get("zh", ""),
                ]
                if part
            )
            lines.append(truncate_display(f"{marker}{preview}", width))
        return lines

    @property
    def current_row_number(self) -> int:
        if not self.rows:
            return 0
        return self.rows[self.selected].row_number

    def render_panel(self) -> None:
        height = self.panel_height()
        width = self.content_width()
        footer = "↑↓ 选择  Space 跳过/恢复  Enter 导入  Esc 返回"
        if self._is_importing:
            footer = "正在导入  Esc 返回"
        if self.missing_fields:
            lines = [
                f"词书      {self.deck_name}",
                f"来源      {self.source_path}",
                f"状态      词表字段缺失：{', '.join(self.missing_fields)}",
            ]
            self.query_one("#content-area", Static).update(text_panel("导入词表", lines, "Esc 返回", height, width=width))
            return

        header = [
            f"词书      {self.deck_name}",
            f"来源      {self.source_path.name if self.source_path else '-'}",
            f"预览      {len(self.rows)} 行  跳过 {len(self.skip_rows)} 行",
        ]
        message_height = 2 if self.message else 0
        row_height = max(1, panel_body_height(height) - len(header) - 1 - message_height)
        self.row_offset = clamp_scroll_offset(len(self.rows), row_height, self.row_offset)
        row_lines = scroll_window(self.row_lines(), row_height, self.row_offset)
        lines = [*header, "", *row_lines]
        if self.message:
            lines.append("")
            lines.append(self.message)
        self.query_one("#content-area", Static).update(text_panel("导入词表", lines, footer, height, width=width))

    def action_back(self) -> None:
        self.cancel_import_worker()
        self.app.pop_screen()

    def on_unmount(self) -> None:
        self.cancel_import_worker()

    def cancel_import_worker(self) -> None:
        """取消仍在运行的导入 worker。"""
        if self._import_worker is not None:
            self._import_worker.cancel()
            self._unregister_worker(self._import_worker)
            self._import_worker = None

    def _register_worker(self, worker) -> None:
        try:
            app = self.app
        except Exception:
            return
        if hasattr(app, "register_worker"):
            app.register_worker(worker)

    def _unregister_worker(self, worker) -> None:
        try:
            app = self.app
        except Exception:
            return
        if hasattr(app, "unregister_worker"):
            app.unregister_worker(worker)

    def content_width(self) -> int:
        return panel_width(self.size.width, 68)

    def panel_height(self) -> int:
        return panel_height(self.size.height, 6, 16)
