"""一键生成 README 素材到 docs/assets/。

用法: python scripts/demo/make_all.py [场景名...]
场景: demo study spelling search stills，不传则全部生成。
依赖: Chrome（渲染 SVG，可用环境变量 CHROME 指定路径）、ffmpeg（合成 GIF）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render import make_gif, svg_to_png

root = HERE.parent.parent
out = root / "docs" / "assets"
names = sys.argv[1:] or ["demo", "study", "spelling", "search", "stills"]
work = Path(tempfile.gettempdir()) / "termi_word_demo"
out.mkdir(parents=True, exist_ok=True)
py = sys.executable
env = {**os.environ, "PYTHONPATH": str(root), "TERMI_WORD_DATA": str(work / "data")}

for name in names:
    frames_dir = work / name
    shutil.rmtree(frames_dir, ignore_errors=True)
    subprocess.run([py, str(HERE / "seed.py"), str(work / "data"), str(root / "termi_data/imports/words.csv")],
                   env=env, check=True, capture_output=True)
    subprocess.run([py, str(HERE / "scenes.py"), name, str(frames_dir)], env=env, check=True)
    frames = json.loads((frames_dir / "frames.json").read_text(encoding="utf-8"))
    if name == "stills":
        for f in frames:
            if f["svg"].startswith("f"):  # 过渡帧不导出
                continue
            svg = frames_dir / f["svg"]
            svg_to_png(svg, out / svg.with_suffix(".png").name, scale=2)
    else:
        pngs = []
        for f in frames:
            svg = frames_dir / f["svg"]
            svg_to_png(svg, svg.with_suffix(".png"), scale=1)
            pngs.append((svg.with_suffix(".png"), f["dur"]))
        make_gif(pngs, out / f"{name}.gif")
    print(name, "done", len(frames), "frames")
