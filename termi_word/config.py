"""Termi Word 配置"""
from pathlib import Path

from termi_word.runtime_paths import RUNTIME_PATHS

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 类型注解，以便静态分析工具和 IDE 正确推导类型与提供补全
DATA_DIR: Path
IMPORTS_DIR: Path
DEFAULT_DB_PATH: Path
DEFAULT_CSV_PATH: Path
DEFAULT_UI_CONFIG_PATH: Path
PATHS_CONFIG_PATH: Path
LOCAL_TIME_CONFIG_PATH: Path

# 配置属性到 RuntimePaths 属性的映射（字典查找 O(1) 优于 if 链 O(n)）
_CONFIG_MAP: dict[str, str | tuple[str, str]] = {
    "DATA_DIR": "data_dir",
    "IMPORTS_DIR": "imports_dir",
    "DEFAULT_DB_PATH": "db_path",
    "DEFAULT_CSV_PATH": ("imports_dir", "words.csv"),
    "DEFAULT_UI_CONFIG_PATH": "ui_config_path",
    "PATHS_CONFIG_PATH": "paths_config_path",
    "LOCAL_TIME_CONFIG_PATH": "local_time_config_path",
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

# 学习默认参数
DEFAULT_DAILY_NEW_TARGET = 20
DEFAULT_REVIEW_SOFT_LIMIT = 100
DEFAULT_DAILY_SPELLING_TARGET = 15
