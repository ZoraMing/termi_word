"""Termi Word 配置"""
from pathlib import Path

from termi_word.runtime_paths import RUNTIME_PATHS

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 类型注解，以便静态分析工具和 IDE 正确推导类型与提供补全
DATA_DIR: Path
IMPORTS_DIR: Path
DEFAULT_DB_PATH: Path
DEFAULT_CSV_PATH: Path

# 配置属性到 RuntimePaths 属性的映射（字典查找 O(1) 优于 if 链 O(n)）
_CONFIG_MAP: dict[str, str | tuple[str, str]] = {
    "DATA_DIR": "data_dir",
    "IMPORTS_DIR": "imports_dir",
    "DEFAULT_DB_PATH": "db_path",
    "DEFAULT_CSV_PATH": ("imports_dir", "words.csv"),
}


def __getattr__(name: str):
    mapping = _CONFIG_MAP.get(name)
    if mapping is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if isinstance(mapping, tuple):
        # 复合路径：(目录属性, 文件名)
        return getattr(RUNTIME_PATHS, mapping[0]) / mapping[1]
    return getattr(RUNTIME_PATHS, mapping)


APP_TITLE = "Termi Word"

# 学习默认参数常量定义
DEFAULT_DAILY_NEW_TARGET = 20        # 每轮新词默认目标数
DEFAULT_REVIEW_SOFT_LIMIT = 100      # 每轮复习默认软上限
DEFAULT_DAILY_SPELLING_TARGET = 15   # 每日拼写默认目标数


# 面板尺寸默认值与用户配置边界范围常量定义
DEFAULT_PANEL_WIDTH = 68         # 内容区域标准显示宽度
DEFAULT_PANEL_HEIGHT = 12        # 内容区域标准显示高度
DEFAULT_PANEL_MIN_HEIGHT = 6     # 默认面板最小高度
DEFAULT_PANEL_MAX_HEIGHT = 16    # 默认面板最大高度

PANEL_MIN_HEIGHT_RANGE = (1, 50)   # panel_min_height 配置校验区间 (MIN, MAX)
PANEL_MAX_HEIGHT_RANGE = (1, 50)   # panel_max_height 配置校验区间 (MIN, MAX)
PANEL_MAX_WIDTH_RANGE = (10, 200)  # panel_max_width 配置校验区间 (MIN, MAX)
