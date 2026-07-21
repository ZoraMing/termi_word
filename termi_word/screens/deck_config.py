"""词书切换、列字段映射与可见性配置二级页面"""
from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path

from textual.app import ComposeResult
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static

IMPORTS_DIR = None

from termi_word.database.repositories import AppRepository
from termi_word.domain.results import ImportResult
from termi_word.services.import_service import ImportRow, ImportService
from termi_word.ui.messages import format_import_result
from termi_word.ui.layout import compute_frame_layout
from termi_word.ui import (
    is_footer_visible,
    render_content_block,
    render_footer,
    field_row,
    rule,
    toggle_footer_visible,
    safe_register_worker,
    safe_unregister_worker,
)

CSV_FIELDS = ["w", "zh", "en", "us", "c", "core", "ex", "exz"]
FIELD_LABELS = {
    "w": "单词映射(w)",
    "zh": "中文映射(zh)",
    "en": "英文映射(en)",
    "us": "音标映射(us)",
    "c": "分类映射(c)",
    "core": "核心映射(core)",
    "ex": "例句映射(ex)",
    "exz": "翻译映射(exz)",
}

class DeckConfigScreen(Screen):
    """词书管理与列名绑定二级页面"""

    can_focus = True

    BINDINGS = [
        ("escape", "back", "返回"),
        ("up", "prev_field", "上"),
        ("down", "next_field", "下"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.last_msg = ""
        self.last_msg_severity = "info"
        self.csv_files: list[str] = []
        self.csv_headers: list[str] = ["(未绑定)"]
        self.active_deck_name = "无"
        self.mapping: dict[str, str] = {}
        self.is_busy = False
        self._save_worker = None
        
        # 页面列表的行定义：(动作类型, 标签, 值)
        self.items: list[tuple[str, str, str]] = []
        self.pending_action = None
        self._pending_deck_key = ""
        self._pending_mapping_key = ""
        self._pending_mapping_label = ""
        self._import_worker = None
        self._is_importing = False

    def compose(self) -> ComposeResult:
        with Static(classes="frame-container"):
            yield Static(id="content-area")
            yield Static(id="message-area")
            yield Static(id="footer-area")

    def on_mount(self) -> None:
        self.scan_csv_files()
        self.load_config()
        self.render_panel()

    def on_key(self, event: Key) -> None:
        # 无条件放行全局搜索快捷键，避免被页面内 Key 消费吞掉
        if self.app.is_search_shortcut(event.key):
            event.stop()
            self.app.open_search()
            return

        if self.is_busy:
            event.stop()
            return

        key = event.key

        # 如果当前有挂起的二次确认动作
        if self.pending_action is not None:
            if key == self.pending_action.confirm_key:
                event.stop()
                action = self.pending_action.action
                self.pending_action = None
                
                # 执行挂起的真实动作
                if action == "sync_deck":
                    self.active_deck_name = self._pending_deck_key.split(":", 1)[1]
                    self._do_sync_deck()
                elif action == "change_mapping":
                    self._do_change_mapping()
                elif action == "execute_import":
                    self.last_msg = "正在同步词包数据中..."
                    self.render_panel()
                    self.start_csv_import()

                return
            elif key == self.pending_action.cancel_key:
                event.stop()
                self.pending_action = None
                self.last_msg = "已取消操作。"
                self.last_msg_severity = "muted"
                self.render_panel()
                return
            else:
                event.stop()
                return

        # 拦截全局 escape 以便退回
        if key == "escape":
            event.stop()
            self.action_back()
            return

        if key in ("question_mark", "?"):
            event.stop()
            toggle_footer_visible(self)
            self.render_panel()
            return

        if key in ("enter", "space"):
            event.stop()
            self.action_select()
            return

    def scan_csv_files(self) -> None:
        """扫描外部导入目录下的所有 CSV 文件。"""
        path = IMPORTS_DIR
        if path is None:
            from termi_word.config import IMPORTS_DIR as cfg_imports_dir
            path = cfg_imports_dir
        self.csv_files = [
            p.name
            for p in sorted(path.glob("*.csv"))
            if not p.name.startswith(".")
        ]

    def load_config(self) -> None:
        """加载数据库配置与当前 CSV Headers"""
        from termi_word.config import IMPORTS_DIR
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            deck = repo.active_deck()
            
            # 加载当前激活词书名称
            if deck:
                self.active_deck_name = f"{deck.name}.csv"
            elif self.csv_files:
                self.active_deck_name = self.csv_files[0]
                # 写入数据库默认活跃词书
                db_deck = repo.get_or_create_deck(Path(self.active_deck_name).stem)
                setting.active_deck_id = db_deck.id
                session.commit()
            else:
                self.active_deck_name = "无可用CSV"

            # 加载映射关系
            self.mapping = {}
            if setting.csv_column_mapping:
                try:
                    self.mapping = json.loads(setting.csv_column_mapping)
                except Exception:
                    pass
            for f in CSV_FIELDS:
                if f not in self.mapping:
                    self.mapping[f] = f  # 默认回退为标准字段

            # 加载展示开关
            self.show_us = bool(setting.show_us)
            self.show_en = bool(setting.show_en)
            self.show_examples = bool(setting.show_examples)

        # 读取当前 CSV 文件的 Headers
        self.csv_headers = ["(未绑定)"]
        if self.active_deck_name != "无可用CSV":
            path = IMPORTS_DIR
            if path is None:
                from termi_word.config import IMPORTS_DIR as cfg_imports_dir
                path = cfg_imports_dir
            csv_path = path / self.active_deck_name
            if csv_path.exists():
                try:
                    with csv_path.open("r", encoding="utf-8-sig") as f:
                        reader = csv.reader(f)
                        first_row = next(reader)
                        if first_row:
                            self.csv_headers.extend([h.strip() for h in first_row if h.strip()])
                except Exception:
                    pass

        self.rebuild_items()

    def rebuild_items(self) -> None:
        """重构显示行"""
        self.items = [
            ("status", "当前使用", self.active_deck_name),
        ]

        for csv_file in self.csv_files:
            marker = "已启用" if csv_file == self.active_deck_name else "按 Enter 启用"
            self.items.append((f"deck:{csv_file}", csv_file, marker))

        self.items.append(("execute_import", "同步当前词书", "按 Enter 导入/更新数据库"))

        # 高级项保留在词书选择之后，避免干扰主流程
        for f in CSV_FIELDS:
            self.items.append((f"map_{f}", FIELD_LABELS[f], self.mapping.get(f) or "(未绑定)"))
        
        # 添加展示项
        self.items.append(("show_us", "显示音标", "是" if self.show_us else "否"))
        self.items.append(("show_en", "显示英文", "是" if self.show_en else "否"))
        self.items.append(("show_examples", "显示例句", "是" if self.show_examples else "否"))
        self.selected = min(self.selected, max(0, len(self.items) - 1))
        
    def apply_dynamic_layout(self, footer_text: str = "") -> tuple[int, int]:
        setting = getattr(self.app, "settings", None)
        if setting is None:
            with self.app.session_factory() as session:
                setting = AppRepository(session).get_settings()
        
        layout = compute_frame_layout(
            terminal_width=self.size.width,
            terminal_height=self.size.height,
            panel_min_height=setting.panel_min_height,
            panel_max_height=setting.panel_max_height,
            panel_max_width=setting.panel_max_width,
            footer_text=footer_text,
            has_input=False,
            message_rows=1,
            footer_visible=is_footer_visible(self),
        )
        
        container = self.query_one(".frame-container", Static)
        container.styles.height = layout.frame_height
        container.styles.min_height = layout.frame_height
        container.styles.max_height = layout.frame_height
        container.styles.width = layout.frame_width
        
        self.query_one("#footer-area", Static).styles.height = layout.footer_rows

        content = self.query_one("#content-area", Static)
        content.styles.height = layout.content_height
        content.styles.min_height = layout.content_height
        content.styles.max_height = layout.content_height
        
        return layout.content_height, layout.content_width

    def on_resize(self) -> None:
        """窗口缩放事件，重新刷新渲染页面。"""
        self.render_panel()

    def render_panel(self) -> None:
        """根据当前配置渲染面板"""
        footer_text = "↑↓ 选择   Enter 启用/同步   词书位置: termi_data/imports/   Esc 返回"
        content_height, width = self.apply_dynamic_layout(footer_text)
        content_widget = self.query_one("#content-area", Static)
        msg_widget = self.query_one("#message-area", Static)
        footer_widget = self.query_one("#footer-area", Static)

        title = "词书配置 / 编辑中" if self.pending_action is not None else "词书配置 / 浏览"
        eff_height = max(1, content_height - 2)

        # 向上/下滚动裁剪计算
        start_idx = 0
        if self.selected >= eff_height:
            start_idx = self.selected - eff_height + 1
        
        body_lines = []
        for index in range(start_idx, min(len(self.items), start_idx + eff_height)):
            key, label, val_str = self.items[index]
            is_sel = index == self.selected
            if key.startswith("deck:") and label == self.active_deck_name:
                label = f"* {label}"
            body_lines.append(
                field_row(label, val_str, selected=is_sel, editing=False, width=16)
            )

        while len(body_lines) < eff_height:
            body_lines.append("")

        lines = [title, rule(width=width)] + body_lines
        content_widget.update(render_content_block(lines, height=content_height, width=width))
        
        # 动态更新消息颜色类
        msg_widget.remove_class("success", "error", "muted")
        if self.last_msg_severity != "info":
            msg_widget.add_class(self.last_msg_severity)

        msg_widget.update(self.last_msg or f"当前使用：{self.active_deck_name}")
        footer_output = render_footer(footer_text, width) if is_footer_visible(self) else ""
        footer_widget.update(footer_output)

    def action_prev_field(self) -> None:
        self.selected = max(0, self.selected - 1)
        self.render_panel()

    def action_next_field(self) -> None:
        self.selected = min(len(self.items) - 1, self.selected + 1)
        self.render_panel()

    def action_back(self) -> None:
        self._cancel_workers()
        self.app.pop_screen()

    def on_unmount(self) -> None:
        self._cancel_workers()

    def action_select(self) -> None:
        """用户确认或修改某项"""
        key, label, val_str = self.items[self.selected]
        
        if key == "status":
            self.last_msg = f"当前正在使用：{self.active_deck_name}"
            self.last_msg_severity = "info"
            self.render_panel()
            return

        from termi_word.ui.keyboard import PendingConfirmation, HIGH_IMPACT_ACTIONS

        # 1. 明确选择词书
        if key.startswith("deck:"):
            deck_name = key.split(":", 1)[1]
            if deck_name == self.active_deck_name:
                self.last_msg = "该词书已处于启用状态"
                self.last_msg_severity = "info"
                self.render_panel()
                return
            self._pending_deck_key = key
            self.pending_action = PendingConfirmation(
                action="sync_deck",
                prompt=HIGH_IMPACT_ACTIONS["sync_deck"]
            )
            self.last_msg = self.pending_action.prompt
            self.last_msg_severity = "info"
            self.render_panel()
            return

        # 2. 字段映射绑定
        if key.startswith("map_"):
            self._pending_mapping_key = key
            self._pending_mapping_label = label
            self.pending_action = PendingConfirmation(
                action="change_mapping",
                prompt=HIGH_IMPACT_ACTIONS["change_mapping"]
            )
            self.last_msg = self.pending_action.prompt
            self.last_msg_severity = "info"
            self.render_panel()
            return

        # 3. 字段可见性控制
        if key in ("show_us", "show_en", "show_examples"):
            self._do_save_visibility(key, label)
            return

        # 4. 执行数据同步导入
        if key == "execute_import":
            self.pending_action = PendingConfirmation(
                action="execute_import",
                prompt=HIGH_IMPACT_ACTIONS["sync_deck"]
            )
            self.last_msg = self.pending_action.prompt
            self.last_msg_severity = "info"
            self.render_panel()
            return

    def start_csv_import(self) -> None:
        """启动词书同步 worker，并阻止重复导入。"""
        if self._is_importing:
            self.last_msg = "词书同步正在进行中，请稍候。"
            self.last_msg_severity = "info"
            self.render_panel()
            return
        self._is_importing = True
        self._import_worker = self.run_worker(self.run_csv_import(), exclusive=True)
        safe_register_worker(self, self._import_worker)

    # ── 异步操作 ──────────────────────────────────────────────

    def _do_sync_deck(self) -> None:
        """异步切换词书：保存选择 → 重载配置 → 启动同步导入。"""
        self.is_busy = True
        self.last_msg = "正在切换词包并解析配置..."
        self.last_msg_severity = "info"
        self.render_panel()
        self._save_worker = self.run_worker(self._async_sync_deck(), exclusive=True)
        safe_register_worker(self, self._save_worker)

    async def _async_sync_deck(self) -> None:
        try:
            deck_stem = Path(self.active_deck_name).stem
            await asyncio.to_thread(self._save_deck_selection_db, deck_stem)
            await asyncio.to_thread(self.load_config)
            self.last_msg = "正在同步词包数据中..."
            self.render_panel()
            self.start_csv_import()
        except Exception as exc:
            self.last_msg = f"切换词包发生错误: {exc}"
            self.last_msg_severity = "error"
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._save_worker)
            self._save_worker = None
            if getattr(self, "is_mounted", True):
                self.render_panel()

    def _save_deck_selection_db(self, deck_stem: str) -> None:
        """保存当前所选词书配置（在后台线程中运行）。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            db_deck = repo.get_or_create_deck(deck_stem)
            setting.active_deck_id = db_deck.id
            session.commit()

    def _do_change_mapping(self) -> None:
        """异步切换字段映射绑定。"""
        self.is_busy = True
        self.last_msg = "正在保存映射关系..."
        self.last_msg_severity = "info"
        self.render_panel()
        self._save_worker = self.run_worker(self._async_change_mapping(), exclusive=True)
        safe_register_worker(self, self._save_worker)

    async def _async_change_mapping(self) -> None:
        field_name = self._pending_mapping_key[4:]
        current_mapping = self.mapping.get(field_name) or "(未绑定)"
        try:
            curr_idx = self.csv_headers.index(current_mapping)
            next_idx = (curr_idx + 1) % len(self.csv_headers)
        except ValueError:
            next_idx = 0
        chosen_header = self.csv_headers[next_idx]
        
        old_mapping = self.mapping.get(field_name)
        if chosen_header == "(未绑定)":
            self.mapping[field_name] = ""
        else:
            self.mapping[field_name] = chosen_header
            
        try:
            await asyncio.to_thread(self._save_mapping_db)
            self.rebuild_items()
            self.last_msg = f"已更改 【{self._pending_mapping_label}】 绑定至 CSV 列: {chosen_header}"
            self.last_msg_severity = "success"
        except Exception as exc:
            self.mapping[field_name] = old_mapping or ""
            self.last_msg = f"更改映射失败: {exc}"
            self.last_msg_severity = "error"
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._save_worker)
            self._save_worker = None
            if getattr(self, "is_mounted", True):
                self.render_panel()

    def _save_mapping_db(self) -> None:
        """保存绑定关系到数据库（在后台线程中运行）。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            setting.csv_column_mapping = json.dumps(self.mapping, ensure_ascii=False)
            session.commit()

    def _do_save_visibility(self, key: str, label: str) -> None:
        """异步保存字段展示状态。"""
        self.is_busy = True
        self.last_msg = "正在更新字段展示..."
        self.last_msg_severity = "info"
        self.render_panel()
        self._save_worker = self.run_worker(self._async_save_visibility(key, label), exclusive=True)
        safe_register_worker(self, self._save_worker)

    async def _async_save_visibility(self, key: str, label: str) -> None:
        if key == "show_us":
            self.show_us = not self.show_us
        elif key == "show_en":
            self.show_en = not self.show_en
        elif key == "show_examples":
            self.show_examples = not self.show_examples

        try:
            await asyncio.to_thread(self._save_visibility_db)
            self.rebuild_items()
            self.last_msg = f"已更新【{label}】展示状态。"
            self.last_msg_severity = "success"
        except Exception as exc:
            # 回滚
            if key == "show_us":
                self.show_us = not self.show_us
            elif key == "show_en":
                self.show_en = not self.show_en
            elif key == "show_examples":
                self.show_examples = not self.show_examples
            self.last_msg = f"保存展示更新失败: {exc}"
            self.last_msg_severity = "error"
        finally:
            self.is_busy = False
            safe_unregister_worker(self, self._save_worker)
            self._save_worker = None
            if getattr(self, "is_mounted", True):
                self.render_panel()

    def _save_visibility_db(self) -> None:
        """保存字段展示状态（在后台线程中运行）。"""
        with self.app.session_factory() as session:
            repo = AppRepository(session)
            setting = repo.get_settings()
            setting.show_us = self.show_us
            setting.show_en = self.show_en
            setting.show_examples = self.show_examples
            session.commit()

    def _cancel_workers(self) -> None:
        """取消仍在运行的后台 worker。"""
        for attr in ("_import_worker", "_save_worker"):
            worker = getattr(self, attr, None)
            if worker is not None:
                worker.cancel()
                setattr(self, attr, None)
        self._is_importing = False
        self.is_busy = False

    async def run_csv_import(self) -> None:
        """执行 CSV 导入至 SQLite 数据库"""
        path = IMPORTS_DIR
        if path is None:
            from termi_word.config import IMPORTS_DIR as cfg_imports_dir
            path = cfg_imports_dir
        deck_stem = Path(self.active_deck_name).stem
        import_service = ImportService(self.app.session_factory, csv_path=path / self.active_deck_name)
        
        try:
            csv_to_use, rows, missing = await asyncio.to_thread(import_service.read_source_rows, deck_stem)
            if not csv_to_use.exists():
                result = ImportResult(source_missing=str(csv_to_use))
            elif missing:
                result = ImportResult(missing_fields=missing)
            else:
                result = await self._import_rows_in_batches(import_service, deck_stem, rows)
            res_msg = format_import_result(result)
            if result.missing_fields:
                self.last_msg = res_msg
                self.last_msg_severity = "error"
            elif result.source_missing:
                self.last_msg = res_msg
                self.last_msg_severity = "error"
            elif result.imported == 0 and result.updated == 0:
                self.last_msg = f"未检测到内容变化：{res_msg}"
                self.last_msg_severity = "muted"
            else:
                self.last_msg = f"同步成功！{res_msg}"
                self.last_msg_severity = "success"
        except Exception as e:
            self.last_msg = f"同步失败（系统异常）: {e}"
            self.last_msg_severity = "error"
        finally:
            self._is_importing = False
            safe_unregister_worker(self, self._import_worker)
            self._import_worker = None
        if getattr(self, "is_mounted", True):
            self.render_panel()

    async def _import_rows_in_batches(
        self,
        import_service: ImportService,
        deck_stem: str,
        rows: list[ImportRow],
    ) -> ImportResult:
        """按批写入数据库，避免一个不可取消的大型 to_thread 任务。"""
        imported = 0
        updated = 0
        skipped = 0
        batch_size = import_service.BATCH_SIZE

        for start in range(0, len(rows), batch_size):
            await asyncio.sleep(0)
            batch = rows[start:start + batch_size]
            partial = await asyncio.to_thread(
                import_service.import_prepared_rows,
                deck_stem,
                batch,
                set(),
            )
            imported += partial.imported
            updated += partial.updated
            skipped += partial.skipped

        return ImportResult(imported=imported, updated=updated, skipped=skipped)
