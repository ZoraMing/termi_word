# 开发与打包

## 从源码运行

建议使用 Python 3.12，发布构建用的也是这个版本。

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows
pip install -r requirements.txt

python -m termi_word
```

开发模式下，数据目录是项目根目录下的 termi_data/，词书放在 termi_data/imports/。设置环境变量 TERMI_WORD_DATA 可以指定其他数据目录。

## 打包

项目使用 Nuitka 的 standalone 模式构建，构建脚本会把 termi_data/imports/words.csv 一起打进去，并生成压缩包。

```bash
pip install nuitka
```

- Windows (PowerShell)：`.\scripts\build.ps1`，生成 output/termi_word_windows.zip
- Linux / macOS (Bash)：`./scripts/build.sh`，生成 output/termi_word_linux_<架构>.tar.gz 或 output/termi_word_mac_<架构>.tar.gz

推送 v 开头的 tag 时，GitHub Actions（.github/workflows/release.yml）会在 Windows、Linux、macOS 上分别构建并发布到 Releases。

## 重新录制 README 演示素材

docs/assets/ 下的 GIF 和截图由 scripts/demo/ 自动生成：用临时数据目录模拟过去几天的学习记录，再用 Textual 的测试驱动按剧本操作程序并逐帧截图。不会读写你自己的 termi_data。

需要 Chrome（渲染截图，可用环境变量 CHROME 指定路径）和 ffmpeg（合成 GIF）。

```bash
python scripts/demo/make_all.py              # 全部重新生成
python scripts/demo/make_all.py demo study   # 只生成指定场景
```

场景有 demo、study、spelling、search、stills，剧本在 scripts/demo/scenes.py。

## 项目结构

```text
termi_word/
├── scripts/
│   ├── build.ps1           # Windows 打包脚本
│   ├── build.sh            # Linux/macOS 打包脚本
│   ├── convert_json.py     # JSON 词表转 CSV
│   └── demo/               # README 演示素材录制脚本
├── docs/
│   └── assets/             # README 图片与 GIF
├── termi_data/
│   └── imports/words.csv   # 内置 850 词
└── termi_word/
    ├── app.py              # TUI 应用入口
    ├── config.py           # 配置与路径映射
    ├── runtime_paths.py    # 运行时数据路径解析
    ├── database/           # 数据库与 ORM 模型
    ├── domain/             # 领域对象
    ├── screens/            # TUI 页面
    ├── services/           # 业务逻辑
    ├── ui/                 # 布局与通用渲染
    └── styles/app.tcss     # 界面样式
```
