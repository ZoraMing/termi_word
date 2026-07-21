"""运行时路径解析。"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    """应用运行所需的外部数据路径。"""

    app_root: Path
    data_dir: Path
    imports_dir: Path
    db_path: Path

    def update_from(self, other: RuntimePaths) -> None:
        """从另一个 RuntimePaths 实例更新自身属性（绕过 frozen 限制）。"""
        for field in (
            "app_root",
            "data_dir",
            "imports_dir",
            "db_path",
        ):
            object.__setattr__(self, field, getattr(other, field))


def _get_real_exe_path() -> Path:
    """获取真实 exe 路径，兼容 Nuitka standalone/onefile 和开发模式。"""
    # Nuitka standalone 模式：sys.executable 就是真实路径
    exe = Path(sys.executable).resolve()
    if exe.suffix.lower() == ".exe" and exe.exists():
        return exe

    # Nuitka onefile 模式：sys.executable 指向临时目录，用 NUITKA_ONEFILE_BINARY
    import os
    nuitka_bin = os.environ.get("NUITKA_ONEFILE_BINARY")
    if nuitka_bin:
        return Path(nuitka_bin).resolve()

    # 备选：sys.argv[0]
    if sys.argv:
        argv0 = Path(sys.argv[0]).resolve()
        if argv0.suffix.lower() == ".exe" and argv0.exists():
            return argv0

    # 最后回退到 cwd
    return Path.cwd()


def resolve_runtime_paths(
    *,
    is_frozen: bool | None = None,
    executable: str | Path | None = None,
    module_file: str | Path | None = None,
) -> RuntimePaths:
    """解析开发态或打包态的数据目录。

    数据目录统一使用 exe（或应用根目录）同级目录下的 termi_data/。
    """
    if is_frozen is not None:
        frozen = is_frozen
    else:
        frozen = (
            bool(getattr(sys, "frozen", False))
            or "__compiled__" in globals()
            or hasattr(sys, "__compiled__")
            or (Path(sys.executable).suffix.lower() == ".exe" and "python" not in Path(sys.executable).stem.lower())
        )

    source_file = Path(module_file or __file__).resolve()

    if executable is not None:
        exe_path = Path(executable).resolve()
    elif frozen:
        exe_path = _get_real_exe_path()
    else:
        exe_path = Path(sys.executable).resolve()

    app_root = exe_path.parent if frozen else source_file.parent.parent

    import os
    env_data = os.environ.get("TERMI_WORD_DATA")
    if env_data:
        data_dir = Path(env_data).resolve()
    else:
        data_dir = app_root / "termi_data"

    imports_dir = data_dir / "imports"

    return RuntimePaths(
        app_root=app_root,
        data_dir=data_dir,
        imports_dir=imports_dir,
        db_path=data_dir / "termi_word.sqlite3",
    )


def ensure_data_directories(paths: RuntimePaths) -> None:
    """创建运行所需的数据目录。"""
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.imports_dir.mkdir(parents=True, exist_ok=True)


def reload_runtime_paths() -> None:
    """重新加载配置，并更新全局 RUNTIME_PATHS 实例。"""
    new_paths = resolve_runtime_paths()
    RUNTIME_PATHS.update_from(new_paths)


def migrate_old_configs_to_db(data_dir: Path, session_factory) -> None:
    """迁移旧的配置文件到数据库（一次性迁移）。"""
    import json
    from termi_word.database.repositories import AppRepository

    # 1. 迁移 local_time.json
    local_time_json = data_dir / "local_time.json"
    if local_time_json.exists():
        try:
            time_data = json.loads(local_time_json.read_text(encoding="utf-8"))
            offset = time_data.get("timezone_offset_minutes")
            if offset is not None:
                with session_factory() as session:
                    repo = AppRepository(session)
                    setting = repo.get_settings()
                    if setting.timezone_offset_minutes is None:
                        setting.timezone_offset_minutes = int(offset)
                        session.commit()
            local_time_json.unlink()
        except Exception:
            pass

    # 2. 迁移 setting.json (旧版本可能有时区和 footer 配置)
    setting_json = data_dir / "setting.json"
    if setting_json.exists():
        try:
            settings = json.loads(setting_json.read_text(encoding="utf-8"))
            with session_factory() as session:
                repo = AppRepository(session)
                setting = repo.get_settings()
                modified = False

                # 迁移时区
                if "timezone_offset_minutes" in settings and setting.timezone_offset_minutes is None:
                    setting.timezone_offset_minutes = int(settings["timezone_offset_minutes"])
                    modified = True

                # 迁移 footer
                if "footer" in settings and not setting.footer:
                    setting.footer = json.dumps(settings["footer"], ensure_ascii=False)
                    modified = True

                if modified:
                    session.commit()
            setting_json.unlink()
        except Exception:
            pass

    # 3. 清理其他旧文件
    for old_file in [
        data_dir / "paths.json",
        data_dir / "ui_config.json",
    ]:
        if old_file.exists():
            try:
                old_file.unlink()
            except Exception:
                pass


RUNTIME_PATHS = resolve_runtime_paths()
