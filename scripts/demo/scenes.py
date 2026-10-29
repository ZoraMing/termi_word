"""各演示场景剧本。用法: python scenes.py <场景名> <输出目录>"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from recorder import run


async def esc(r, dur: float = 0.8) -> None:
    # 两次 Esc 间隔需大于 0.8s，否则触发双击退出
    await r.key("escape", wait=1.0)
    await r.shot(dur)


async def review_cards(r, ratings: str) -> None:
    for i, rating in enumerate(ratings):
        await r.shot(1.2 if i == 0 else 0.9)
        await r.key(rating)
        await r.shot(2.0)
        await r.key("enter", wait=0.8)


async def spell_word(r, typo: bool = False) -> None:
    word = r.app.screen.current_word.w
    await r.shot(1.4)
    if typo:
        await r.type(word[:-2] + word[-1] + word[-2], dur=0.18)
    else:
        await r.type(word, dur=0.18)
    await r.key("enter", wait=0.6)
    await r.shot(1.8)
    await r.key("enter", wait=0.5)


async def demo(r) -> None:
    await r.shot(2.0)
    await r.key("2", wait=1.2)
    await review_cards(r, "343")
    await r.shot(0.8)
    await esc(r, 2.0)
    await r.key("3", wait=1.0)
    await spell_word(r)
    await r.shot(0.8)
    await esc(r, 0.6)
    await r.key("ctrl+slash", wait=0.8)
    await r.shot(0.8)
    await r.type("bre", dur=0.3, wait=0.6)
    await r.shot(0.6)
    await r.key("down")
    await r.shot(1.5)
    await esc(r, 0.3)
    await esc(r, 0.6)
    await r.key("5", wait=1.0)
    await r.shot(2.5)
    await esc(r, 2.0)


async def study(r) -> None:
    await r.shot(1.5)
    await r.key("2", wait=1.2)
    await review_cards(r, "3241")
    await r.shot(1.5)


async def spelling(r) -> None:
    await r.key("3", wait=1.0)
    await spell_word(r)
    await spell_word(r, typo=True)
    await r.shot(1.0)


async def search(r) -> None:
    await r.shot(1.2)
    await r.key("ctrl+slash", wait=0.8)
    await r.shot(1.0)
    await r.type("ex", dur=0.35, wait=0.6)
    await r.shot(0.8)
    for _ in range(2):
        await r.key("down")
        await r.shot(0.9)
    await r.key("enter")
    await r.shot(1.2)
    for _ in range(3):
        await r.key("down")
        await r.shot(0.7)
    await r.shot(1.2)


async def stills(r) -> None:
    """README 静态截图：学完几张卡后各页面的样子。"""
    await r.key("2", wait=1.2)
    await r.key("3", wait=0.4)
    await r.shot(name="study")
    await r.key("enter", wait=0.8)
    await r.key("4", "enter", "3", "enter", wait=0.8)
    await esc(r)
    await r.shot(name="home")
    await r.key("3", wait=1.0)
    word = r.app.screen.current_word.w
    for ch in word[:3]:
        await r.pilot.press(ch)
    await r.pilot.pause(0.3)
    await r.shot(name="spelling")
    await esc(r)
    await r.key("4", wait=1.0)
    await r.shot(name="words")
    await esc(r)
    await r.key("5", wait=1.0)
    await r.shot(name="calendar")
    await esc(r)
    await r.key("6", wait=1.0)
    await r.shot(name="settings")


SCENES = {"demo": demo, "study": study, "spelling": spelling, "search": search, "stills": stills}

if __name__ == "__main__":
    asyncio.run(run(SCENES[sys.argv[1]], Path(sys.argv[2])))
