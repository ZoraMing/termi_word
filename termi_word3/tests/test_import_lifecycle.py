"""导入页 worker 生命周期回归测试。"""
from __future__ import annotations

import inspect
import unittest

from termi_word3.screens.import_panel import ImportScreen
from termi_word3.screens.deck_config import DeckConfigScreen


class FakeWorker:
    """记录 cancel 调用的轻量 worker 替身。"""

    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class TestImportScreenLifecycle(unittest.TestCase):
    """验证导入页不会阻塞 UI 线程，并能取消后台 worker。"""

    def make_screen(self) -> tuple[ImportScreen, FakeWorker, list[object]]:
        screen = ImportScreen.__new__(ImportScreen)
        worker = FakeWorker()
        calls: list[object] = []

        screen.deck_name = "demo"
        screen.skip_rows = {2}
        screen.message = ""
        screen._is_importing = False
        screen._import_worker = None
        screen.render_panel = lambda: None

        def run_worker(*args, **kwargs):
            for arg in args:
                if inspect.iscoroutine(arg):
                    arg.close()
            calls.append((args, kwargs))
            return worker

        screen.run_worker = run_worker
        return screen, worker, calls

    def test_import_rows_runs_worker_without_sync_service_call(self) -> None:
        screen, worker, calls = self.make_screen()

        screen.import_rows()

        self.assertTrue(screen._is_importing)
        self.assertEqual(screen.message, "正在导入词表...")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1]["exclusive"])
        self.assertIs(screen._import_worker, worker)

    def test_import_rows_ignores_reentry(self) -> None:
        screen, _, calls = self.make_screen()
        screen._is_importing = True

        screen.import_rows()

        self.assertEqual(calls, [])

    def test_cancel_import_worker_cancels_import_worker(self) -> None:
        screen, worker, _ = self.make_screen()
        screen._import_worker = worker

        screen.cancel_import_worker()

        self.assertTrue(worker.cancelled)
        self.assertIsNone(screen._import_worker)


class TestDeckConfigImportLifecycle(unittest.TestCase):
    """验证词书配置页同步 worker 防重入与取消。"""

    def make_screen(self) -> tuple[DeckConfigScreen, FakeWorker, list[object]]:
        screen = DeckConfigScreen.__new__(DeckConfigScreen)
        worker = FakeWorker()
        calls: list[object] = []

        screen._is_importing = False
        screen._import_worker = None
        screen.last_msg = ""
        screen.last_msg_severity = "info"
        screen.render_panel = lambda: None

        def run_worker(*args, **kwargs):
            for arg in args:
                if inspect.iscoroutine(arg):
                    arg.close()
            calls.append((args, kwargs))
            return worker

        screen.run_worker = run_worker
        return screen, worker, calls

    def test_start_csv_import_runs_worker(self) -> None:
        screen, worker, calls = self.make_screen()

        screen.start_csv_import()

        self.assertTrue(screen._is_importing)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1]["exclusive"])
        self.assertIs(screen._import_worker, worker)

    def test_start_csv_import_ignores_reentry(self) -> None:
        screen, worker, calls = self.make_screen()
        screen._is_importing = True
        screen._import_worker = worker

        screen.start_csv_import()

        self.assertEqual(calls, [])
        self.assertIs(screen._import_worker, worker)
        self.assertEqual(screen.last_msg, "词书同步正在进行中，请稍候。")

    def test_cancel_import_worker_cancels_worker(self) -> None:
        screen, worker, _ = self.make_screen()
        screen._is_importing = True
        screen._import_worker = worker

        screen.cancel_import_worker()

        self.assertTrue(worker.cancelled)
        self.assertFalse(screen._is_importing)
        self.assertIsNone(screen._import_worker)

    def test_unmount_cancels_import_worker(self) -> None:
        screen, worker, _ = self.make_screen()
        screen._import_worker = worker

        screen.on_unmount()

        self.assertTrue(worker.cancelled)
        self.assertIsNone(screen._import_worker)


if __name__ == "__main__":
    unittest.main()
