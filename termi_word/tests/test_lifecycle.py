"""应用退出与屏幕 worker 生命周期回归测试。"""
from __future__ import annotations

import inspect
import unittest

from termi_word.app import TermiWordApp
from termi_word.screens.review import ReviewScreen


class FakeWorker:
    """记录 cancel 调用的轻量 worker 替身。"""

    def __init__(self) -> None:
        self.cancelled = False
        self.cancel_count = 0

    def cancel(self) -> None:
        self.cancelled = True
        self.cancel_count += 1


class FakeEngine:
    """记录 dispose 调用的轻量 engine 替身。"""

    def __init__(self) -> None:
        self.disposed = False
        self.dispose_count = 0

    def dispose(self) -> None:
        self.disposed = True
        self.dispose_count += 1


class FakeSessionFactory:
    """模拟 SQLAlchemy sessionmaker 暴露的 kw['bind']。"""

    def __init__(self, engine: FakeEngine) -> None:
        self.kw = {"bind": engine}


class TestAppLifecycle(unittest.TestCase):
    """验证应用退出路径集中清理后台任务和数据库连接。"""

    def test_request_exit_cancels_workers_and_disposes_engine(self) -> None:
        app = TermiWordApp.__new__(TermiWordApp)
        first_worker = FakeWorker()
        second_worker = FakeWorker()
        engine = FakeEngine()
        exited: list[bool] = []

        app._bootstrap_worker = first_worker
        app._study_worker = second_worker
        app._engine = engine
        app._managed_workers = []
        app._is_exiting = False
        app.exit = lambda: exited.append(True)

        app.request_exit()

        self.assertTrue(first_worker.cancelled)
        self.assertTrue(second_worker.cancelled)
        self.assertTrue(engine.disposed)
        self.assertEqual(exited, [True])

    def test_request_exit_is_idempotent(self) -> None:
        app = TermiWordApp.__new__(TermiWordApp)
        worker = FakeWorker()
        engine = FakeEngine()
        exited: list[bool] = []

        app._bootstrap_worker = worker
        app._study_worker = None
        app._engine = engine
        app._managed_workers = []
        app._is_exiting = False
        app.exit = lambda: exited.append(True)

        app.request_exit()
        app.request_exit()

        self.assertEqual(worker.cancel_count, 1)
        self.assertEqual(engine.dispose_count, 1)
        self.assertEqual(exited, [True])

    def test_request_exit_cancels_registered_screen_workers(self) -> None:
        app = TermiWordApp.__new__(TermiWordApp)
        screen_worker = FakeWorker()
        engine = FakeEngine()
        exited: list[bool] = []

        app._bootstrap_worker = None
        app._study_worker = None
        app._engine = engine
        app._managed_workers = []
        app._is_exiting = False
        app.exit = lambda: exited.append(True)

        app.register_worker(screen_worker)
        app.request_exit()

        self.assertTrue(screen_worker.cancelled)
        self.assertEqual(app._managed_workers, [])
        self.assertEqual(exited, [True])

    def test_exit_shortcuts_use_request_exit(self) -> None:
        for key in ("ctrl+q", "ctrl+z"):
            with self.subTest(key=key):
                app = TermiWordApp.__new__(TermiWordApp)
                event = FakeKeyEvent(key)
                requested: list[str] = []

                app.request_exit = lambda: requested.append(key)

                app.on_key(event)

                self.assertTrue(event.stopped)
                self.assertEqual(requested, [key])

    def test_ctrl_c_does_not_exit(self) -> None:
        app = TermiWordApp.__new__(TermiWordApp)
        app.is_search_shortcut = lambda key: False
        event = FakeKeyEvent("ctrl+c")
        requested: list[str] = []
        app.request_exit = lambda: requested.append("ctrl+c")

        app.on_key(event)

        self.assertFalse(event.stopped)
        self.assertEqual(requested, [])


class TestReviewLifecycle(unittest.TestCase):
    """验证复习屏后台自动切词 worker 的生命周期管理。"""

    @staticmethod
    def record_worker(calls: list[object], worker: FakeWorker):
        def run_worker(*args, **kwargs):
            for arg in args:
                if inspect.iscoroutine(arg):
                    arg.close()
            calls.append((args, kwargs))
            return worker

        return run_worker

    def test_skip_ignores_reentry_while_auto_advance_is_waiting(self) -> None:
        screen = ReviewScreen.__new__(ReviewScreen)
        worker = FakeWorker()
        calls: list[object] = []

        screen._waiting = True
        screen._auto_advance_worker = worker
        screen.run_worker = self.record_worker(calls, worker)

        screen._do_auto_advance()

        self.assertEqual(calls, [])
        self.assertIs(screen._auto_advance_worker, worker)

    def test_unmount_cancels_auto_advance_worker(self) -> None:
        screen = ReviewScreen.__new__(ReviewScreen)
        worker = FakeWorker()
        screen._auto_advance_worker = worker

        screen.on_unmount()

        self.assertTrue(worker.cancelled)
        self.assertIsNone(screen._auto_advance_worker)

    def test_start_extra_study_runs_worker(self) -> None:
        screen = ReviewScreen.__new__(ReviewScreen)
        worker = FakeWorker()
        calls: list[object] = []

        screen._extra_study_worker = None
        screen._is_loading_extra = False
        screen._has_extra_option = True
        screen.feedback = ""
        screen.render_card = lambda: None
        screen.run_worker = self.record_worker(calls, worker)

        screen._start_extra_study()

        self.assertFalse(screen._has_extra_option)
        self.assertEqual(screen.feedback, "正在加载额外学习队列...")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1]["exclusive"])
        self.assertIs(screen._extra_study_worker, worker)

    def test_start_extra_study_ignores_reentry(self) -> None:
        screen = ReviewScreen.__new__(ReviewScreen)
        worker = FakeWorker()
        calls: list[object] = []

        screen._extra_study_worker = worker
        screen.run_worker = self.record_worker(calls, worker)

        screen._start_extra_study()

        self.assertEqual(calls, [])
        self.assertIs(screen._extra_study_worker, worker)

    def test_unmount_cancels_all_review_workers(self) -> None:
        screen = ReviewScreen.__new__(ReviewScreen)
        auto_worker = FakeWorker()
        extra_worker = FakeWorker()
        screen._auto_advance_worker = auto_worker
        screen._extra_study_worker = extra_worker

        screen.on_unmount()

        self.assertTrue(auto_worker.cancelled)
        self.assertTrue(extra_worker.cancelled)
        self.assertIsNone(screen._auto_advance_worker)
        self.assertIsNone(screen._extra_study_worker)


class FakeKeyEvent:
    """记录 stop 调用的轻量 Key 事件替身。"""

    def __init__(self, key: str) -> None:
        self.key = key
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


if __name__ == "__main__":
    unittest.main()
