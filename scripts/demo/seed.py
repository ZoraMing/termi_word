"""在 TERMI_WORD_DATA 指向的临时目录中生成演示数据：过去 6 天的学习/拼写记录。"""
import random
import shutil
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

data_dir = Path(sys.argv[1])
csv_src = Path(sys.argv[2])
if data_dir.exists():
    shutil.rmtree(data_dir)
(data_dir / "imports").mkdir(parents=True)
shutil.copy(csv_src, data_dir / "imports" / "words.csv")

import os
os.environ["TERMI_WORD_DATA"] = str(data_dir)

from sqlalchemy import select
from termi_word.config import DEFAULT_DB_PATH
from termi_word.database.engine import create_session_factory, init_database
from termi_word.database.models import Card, SpellingLog, Word
from termi_word.services.import_service import ImportService
from termi_word.services.scheduler_service import SchedulerService
from termi_word.services.time_service import TimeSettingsService

random.seed(7)
sf = create_session_factory(DEFAULT_DB_PATH)
init_database(sf)
offset = TimeSettingsService(sf).ensure_config().timezone_offset_minutes
ImportService(sf).ensure_initial_data()

local_now = datetime.now().astimezone()
clock = [local_now]
scheduler = SchedulerService(now=lambda: clock[0], timezone_offset_minutes=offset)


def rate() -> int:
    return random.choices([1, 2, 3, 4], weights=[8, 15, 62, 15])[0]


def review_due(session) -> None:
    now_utc = clock[0].astimezone(timezone.utc).replace(tzinfo=None)
    due = session.execute(select(Card).where(Card.reps > 0, Card.due <= now_utc)).scalars().all()
    for card in due:
        session.add(scheduler.review(card, rate()))
        clock[0] += timedelta(seconds=25)


with sf() as session:
    new_cards = [c for c in session.execute(select(Card).join(Word).order_by(Word.id)).scalars() if len(c.word.w) >= 4]
    random.shuffle(new_cards)
    cursor = 0
    for days_ago in range(6, 0, -1):
        day = (local_now - timedelta(days=days_ago)).date()
        clock[0] = datetime.combine(day, time(20, 30), tzinfo=local_now.tzinfo)
        review_due(session)
        for card in new_cards[cursor:cursor + 20]:
            session.add(scheduler.review(card, rate()))
            clock[0] += timedelta(seconds=30)
        cursor += 20
        clock[0] += timedelta(minutes=15)
        review_due(session)
        learned = session.execute(
            select(Word).join(Card).where(Card.reps > 0).order_by(Word.id)
        ).scalars().all()
        for word in random.sample(learned, 15):
            ok = random.random() < 0.85
            session.add(SpellingLog(
                word_id=word.id,
                input_spelling=word.w if ok else word.w[:-1],
                is_correct=ok,
                hint_used_count=0 if ok else 1,
                tested_at=clock[0].astimezone(timezone.utc).replace(tzinfo=None),
            ))
            clock[0] += timedelta(seconds=20)
        session.commit()

    for word in session.execute(select(Word).order_by(Word.id).limit(40)).scalars().all()[::7]:
        word.is_starred = True
    session.commit()
    print(f"learned={cursor}")
