"""运行时路径解析。"""
from __future__ import annotations

import sys
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    """应用运行所需的外部数据路径。"""

    app_root: Path
    bootstrap_dir: Path
    data_dir: Path
    imports_dir: Path
    db_path: Path
    ui_config_path: Path
    local_time_config_path: Path
    paths_config_path: Path

    def update_from(self, other: RuntimePaths) -> None:
        """从另一个 RuntimePaths 实例更新自身属性（绕过 frozen 限制）。"""
        for field in (
            "app_root",
            "bootstrap_dir",
            "data_dir",
            "imports_dir",
            "db_path",
            "ui_config_path",
            "local_time_config_path",
            "paths_config_path",
        ):
            object.__setattr__(self, field, getattr(other, field))


def resolve_runtime_paths(
    *,
    is_frozen: bool | None = None,
    executable: str | Path | None = None,
    module_file: str | Path | None = None,
) -> RuntimePaths:
    """解析开发态或打包态的数据目录。

    打包态使用可执行文件所在目录；开发态使用项目根目录。

    注意：Nuitka --onefile 模式下 sys.executable 指向临时解压目录内部，
    必须用 sys.argv[0] 获取用户实际点击的真实 exe 路径，
    否则 paths.json 会写到每次运行都不同的临时目录，导致配置重启后丢失。
    """
    frozen = bool(getattr(sys, "frozen", False)) if is_frozen is None else is_frozen
    source_file = Path(module_file or __file__).resolve()

    if executable is not None:
        # 调用者显式指定，直接使用
        exe_path = Path(executable).resolve()
    elif frozen:
        # Nuitka onefile：sys.executable 指向临时解压目录，需用 sys.argv[0] 获取真实 exe
        real_exe = Path(sys.argv[0]).resolve() if sys.argv else Path(sys.executable).resolve()
        # 若 sys.argv[0] 与 sys.executable 在同一目录（非 onefile），直接用 sys.executable
        exe_path = real_exe
    else:
        exe_path = Path(sys.executable).resolve()

    app_root = exe_path.parent if frozen else source_file.parent.parent
    bootstrap_dir = app_root / "data"
    paths_config_path = bootstrap_dir / "paths.json"
    data_dir = bootstrap_dir
    imports_dir = data_dir / "imports"

    overrides = _load_path_overrides(paths_config_path, app_root)
    if overrides.get("config_dir"):
        data_dir = overrides["config_dir"]
    if overrides.get("imports_dir"):
        imports_dir = overrides["imports_dir"]

    return RuntimePaths(
        app_root=app_root,
        bootstrap_dir=bootstrap_dir,
        data_dir=data_dir,
        imports_dir=imports_dir,
        db_path=data_dir / "termi_word.sqlite3",
        ui_config_path=data_dir / "ui_config.json",
        local_time_config_path=data_dir / "local_time.json",
        paths_config_path=paths_config_path,
    )


def ensure_data_directories(paths: RuntimePaths) -> None:
    """创建运行所需的数据目录，不主动创建数据库文件。"""
    paths.bootstrap_dir.mkdir(parents=True, exist_ok=True)
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.imports_dir.mkdir(parents=True, exist_ok=True)


def _clean_path_string(path_str: str) -> str:
    """清理路径字符串中的引号和首尾空格。"""
    if not path_str:
        return ""
    return path_str.strip().strip("'\"").strip()


def _try_make_relative(path: Path, base_dir: Path) -> str:
    """尝试将路径转换为相对于 base_dir 的相对路径以提供最大便携性。"""
    try:
        p_abs = path.resolve()
        b_abs = base_dir.resolve()
        rel_path = p_abs.relative_to(b_abs)
        return rel_path.as_posix()
    except ValueError:
        return path.resolve().as_posix()


def save_runtime_path_overrides(
    *,
    app_root: str | Path,
    data_dir: str | Path,
) -> Path:
    """保存用户配置的数据目录（imports 子目录自动创建）。"""
    app_root = Path(app_root).expanduser().resolve()
    data_path = _resolve_user_path(data_dir, app_root)
    imports_path = data_path / "imports"
    bootstrap_dir = app_root / "data"
    paths_config_path = bootstrap_dir / "paths.json"

    bootstrap_dir.mkdir(parents=True, exist_ok=True)
    data_path.mkdir(parents=True, exist_ok=True)
    imports_path.mkdir(parents=True, exist_ok=True)

    data_val = _try_make_relative(data_path, app_root)

    paths_config_path.write_text(
        json.dumps(
            {
                "config_dir": data_val,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    reload_runtime_paths()
    return paths_config_path


def _resolve_user_path(path: str | Path, base_dir: Path) -> Path:
    cleaned = _clean_path_string(str(path))
    user_path = Path(cleaned).expanduser()
    if not user_path.is_absolute():
        user_path = base_dir / user_path
    return user_path.resolve()


def _load_path_overrides(paths_config_path: Path, app_root: Path) -> dict[str, Path]:
    if not paths_config_path.exists():
        return {}
    try:
        data = json.loads(paths_config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    overrides: dict[str, Path] = {}
    # 读取 config_dir（数据目录），imports_dir 自动设为其下的 imports 子目录
    raw = str(data.get("config_dir") or "").strip()
    if raw:
        config_path = _resolve_user_path(raw, app_root)
        overrides["config_dir"] = config_path
        overrides["imports_dir"] = config_path / "imports"
    return overrides


def reload_runtime_paths() -> None:
    """重新加载 paths.json 配置，并更新全局 RUNTIME_PATHS 实例。"""
    new_paths = resolve_runtime_paths()
    RUNTIME_PATHS.update_from(new_paths)


RUNTIME_PATHS = resolve_runtime_paths()
