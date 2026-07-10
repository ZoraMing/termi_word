"""性能问题、退出卡顿与光标抢占问题的基准测试与分析。"""
from __future__ import annotations

import asyncio
import datetime
import time
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 导入应用中的组件
from termi_word3.database.models import Base, Word, Deck, Setting
from termi_word3.screens.words import score_word_search, WordEntry


class TestPerformanceAndLifecycle(unittest.TestCase):
    """用于分析和指出应用潜在性能瓶颈、生命周期以及后台协程问题的测试类。"""

    def setUp(self) -> None:
        # 使用内存 SQLite 数据库模拟真实数据库，避免污染本地文件
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        # 预载一些模拟数据
        with self.session_factory() as session:
            deck = Deck(name="TestDeck")
            session.add(deck)
            session.commit()

            setting = Setting(
                daily_new_target=10,
                review_soft_limit=20,
                daily_spelling_target=10,
                panel_min_height=6,
                panel_max_height=16,
                panel_max_width=80,
                show_us=True,
                show_en=True,
                show_examples=True,
            )
            session.add(setting)
            session.commit()
            
            # 生成 5000 个单词来模拟较大数据量的单词本
            words = []
            for i in range(5000):
                words.append(
                    Word(
                        deck_id=deck.id,
                        w=f"wordtest{i}",
                        normalized_word=f"wordtest{i}",
                        zh=f"测试单词解释{i}",
                        core="核心词汇",
                        en=f"English definition for testing word {i}",
                        us=f"phonetic_{i}",
                        c="GRE",
                    )
                )
            session.bulk_save_objects(words)
            session.commit()

    def test_search_match_performance(self) -> None:
        """测试每次按键触发打分排序在大数据量（5000个词）下的 CPU 耗时瓶颈。
        该测试模拟用户输入字符时的同步过滤。
        """
        # 1. 模拟加载全部 5000 个词到内存
        with self.session_factory() as session:
            words = session.query(Word).all()
            entries = [
                WordEntry(
                    word=w,
                    search_text=" ".join([w.w, w.zh, w.core or "", w.en or "", w.c or ""]).lower(),
                    status="新词",
                )
                for w in words
            ]

        # 2. 模拟搜索输入
        query = "test"
        
        start_time = time.perf_counter()
        
        # 模拟 `apply_filter` 在每次击键时的同步打分与排序逻辑
        scored = [(score_word_search(e.word.w, e.word.zh or "", e.search_text, query), e) for e in entries]
        sorted_entries = [
            e
            for score, e in sorted(scored, key=lambda item: item[0], reverse=True)
            if score > 0
        ]
        results = sorted_entries[:200]
        
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        
        print(f"\n[性能测试] 匹配并排序 5000 个单词耗时: {elapsed_ms:.2f} ms")
        
        # 如果单次耗时过高，在多次连续快速输入时累积会造成严重的 UI 帧率下降（通常 UI 交互要在 16ms 内响应以达到 60fps）
        self.assertTrue(len(results) > 0)
        self.assertLess(elapsed_ms, 50.0)

    def test_redundant_db_reads(self) -> None:
        """测试在频繁渲染更新（例如列表滚动 50 次）时，
        每次渲染都同步打开连接读取设置（`apply_dynamic_layout`）的累积 I/O 开销。
        """
        iterations = 50
        
        start_time = time.perf_counter()
        
        # 模拟在 50 次滚动更新中，每一次 render 都会同步读取设置的操作
        for _ in range(iterations):
            with self.session_factory() as session:
                setting = session.query(Setting).first()
                _ = setting.panel_min_height
                _ = setting.panel_max_height
                _ = setting.panel_max_width

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        avg_ms = elapsed_ms / iterations
        
        print(f"[性能测试] 连续同步读取 SQLite 数据库设置 {iterations} 次，总耗时: {elapsed_ms:.2f} ms，平均每次: {avg_ms:.2f} ms")
        self.assertGreater(elapsed_ms, 0)
        self.assertLess(avg_ms, 5.0)

    def test_unclosed_workers_effect_simulation(self) -> None:
        """模拟 ReviewScreen 异步切词 Worker。
        演示当屏幕关闭（例如通过 Esc 返回）后，未取消的 asyncio 协程仍然后台存活并继续尝试修改对象属性的潜在问题。
        """
        class MockScreen:
            def __init__(self):
                self.index = 0
                self.is_active = True
                self.rendered_count = 0

            def render_card(self):
                # 模拟 UI 渲染，如果已经不是 active 状态，则不应再进行渲染，否则会引发异常或焦点异常
                if not self.is_active:
                    raise RuntimeError("警告：已销毁的屏幕仍在尝试渲染并操作数据！")
                self.rendered_count += 1

            async def auto_advance(self):
                await asyncio.sleep(0.05)  # 模拟 1 秒等待的缩短版
                self.index += 1
                self.render_card()

        screen = MockScreen()
        
        # 1. 模拟开启了后台切词协程
        loop = asyncio.new_event_loop()
        task = loop.create_task(screen.auto_advance())
        
        # 2. 模拟用户在此期间按了 Esc 键退出了当前屏
        screen.is_active = False  # 模拟被 pop_screen 销毁
        
        # 3. 协程在 1 秒后醒来试图操作已经销毁的屏幕
        try:
            loop.run_until_complete(task)
            # 如果没有捕获到错误，说明协程静默地修改了属性，但对于真实的 Textual 而言可能破坏了界面状态或焦点
        except RuntimeError as e:
            print(f"[生命周期测试] 检测到预期的残留 Worker 冲突: {e}")
            self.assertIn("已销毁的屏幕", str(e))
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
