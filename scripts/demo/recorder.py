"""用 Textual Pilot 驱动 TermiWordApp，按剧本逐步截取 SVG 帧。"""
import json
from pathlib import Path

from termi_word.app import TermiWordApp

SIZE = (76, 16)


class Recorder:
    def __init__(self, app, pilot, out: Path) -> None:
        self.app, self.pilot, self.out = app, pilot, out
        self.frames: list[dict] = []
        out.mkdir(parents=True, exist_ok=True)

    async def shot(self, dur: float = 1.0, name: str | None = None) -> None:
        await self.pilot.pause(0.15)
        name = name or f"f{len(self.frames):03d}"
        self.app.save_screenshot(filename=f"{name}.svg", path=str(self.out))
        self.frames.append({"svg": f"{name}.svg", "dur": dur})

    async def key(self, *keys: str, wait: float = 0.35) -> None:
        for k in keys:
            await self.pilot.press(k)
            await self.pilot.pause(wait)

    async def type(self, text: str, dur: float = 0.12, wait: float = 0.05) -> None:
        """逐字输入，每个字符截一帧。"""
        for ch in text:
            await self.pilot.press(ch)
            await self.pilot.pause(wait)
            await self.shot(dur)

    async def wait_screen(self, name: str, timeout: float = 10) -> None:
        for _ in range(int(timeout / 0.1)):
            if self.app.screen.__class__.__name__ == name:
                break
            await self.pilot.pause(0.1)
        await self.pilot.pause(0.5)

    def save(self) -> None:
        (self.out / "frames.json").write_text(json.dumps(self.frames, ensure_ascii=False, indent=1), encoding="utf-8")


async def run(scenario, out: Path) -> None:
    app = TermiWordApp()
    async with app.run_test(size=SIZE) as pilot:
        rec = Recorder(app, pilot, out)
        await rec.wait_screen("TodayScreen")
        await scenario(rec)
        rec.save()
