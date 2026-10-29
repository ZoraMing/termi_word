"""Textual SVG 截图后处理与渲染：修正 CJK 宽度，转 PNG，合成 GIF。"""
import html
import math
import os
import re
import subprocess
from pathlib import Path

from rich.cells import cell_len

CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
TEXT_RE = re.compile(r'<text\b([^>]*?) x="([\d.]+)"([^>]*?) textLength="([\d.]+)"([^>]*)>([^<]*)</text>')
VIEWBOX_RE = re.compile(r'viewBox="0 0 ([\d.]+) ([\d.]+)"')


def fix_svg(src: Path, dst: Path) -> tuple[int, int]:
    """Rich 按字符数计算 textLength，中文会被压缩重叠；这里按终端格子给每个字符单独定位。"""
    svg = src.read_text(encoding="utf-8")
    char_width = None
    for m in TEXT_RE.finditer(svg):
        text = html.unescape(m.group(6))
        if text and cell_len(text) == len(text):
            char_width = float(m.group(4)) / len(text)
            break
    # Rich 导出时 char_width = font_size * 0.61，中文字形宽度约等于 font_size，居中放进两格
    wide_offset = (2 * char_width - char_width / 0.61) / 2

    def repl(m: re.Match) -> str:
        text = html.unescape(m.group(6))
        if not text or cell_len(text) == len(text):
            return m.group(0)
        cur, xs = float(m.group(2)), []
        for ch in text:
            w = cell_len(ch)
            xs.append(round(cur + (wide_offset if w == 2 else 0), 2))
            cur += w * char_width
        return f'<text{m.group(1)} x="{" ".join(map(str, xs))}"{m.group(3)}{m.group(5)}>{m.group(6)}</text>'

    svg = TEXT_RE.sub(repl, svg)
    vb = VIEWBOX_RE.search(svg)
    w, h = math.ceil(float(vb.group(1))), math.ceil(float(vb.group(2)))
    svg = svg.replace('<svg class="rich-terminal"', f'<svg width="{w}" height="{h}" class="rich-terminal"', 1)
    # 加上微软雅黑作为中文回退字体，保证各机器渲染一致
    svg = svg.replace("font-family: Fira Code, monospace;", 'font-family: "Fira Code", "Microsoft YaHei", monospace;')
    dst.write_text(svg, encoding="utf-8")
    return w, h


def svg_to_png(svg: Path, png: Path, scale: float = 1.0) -> None:
    w, h = fix_svg(svg, svg.with_suffix(".fixed.svg"))
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--force-device-scale-factor={scale}", f"--window-size={w},{h}",
            f"--screenshot={png}", svg.with_suffix(".fixed.svg").resolve().as_uri(),
        ],
        check=True, capture_output=True,
    )


def make_gif(frames: list[tuple[Path, float]], out: Path, width: int = 900) -> None:
    """frames: [(png, 停留秒数)]，用 ffmpeg 两遍调色板合成 GIF。"""
    concat = out.with_suffix(".txt")
    lines = []
    for png, dur in frames:
        lines.append(f"file '{png.resolve().as_posix()}'\nduration {dur}")
    lines.append(f"file '{frames[-1][0].resolve().as_posix()}'")
    concat.write_text("\n".join(lines), encoding="utf-8")
    vf = (f"scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
         "-vf", vf, "-loop", "0", str(out)],
        check=True,
    )
    concat.unlink()
