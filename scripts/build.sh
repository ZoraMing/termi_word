#!/usr/bin/env sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON:-}"

# 只使用本地虚拟环境
if [ -z "$PYTHON" ]; then
    if [ -n "${VIRTUAL_ENV:-}" ]; then
        PYTHON="python"
    elif [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
        PYTHON="$PROJECT_ROOT/.venv/bin/python"
    elif [ -x "$PROJECT_ROOT/.venv_build/bin/python" ]; then
        PYTHON="$PROJECT_ROOT/.venv_build/bin/python"
    else
        PYTHON="python3"
    fi
fi

PACKAGE_ROOT="${PACKAGE_ROOT:-$PROJECT_ROOT/.nuitka-package}"
OUTPUT_DIR="$PACKAGE_ROOT/output"
CACHE_ROOT="$PACKAGE_ROOT/cache"
TEMP_ROOT="$PACKAGE_ROOT/temp"
mkdir -p "$OUTPUT_DIR" "$CACHE_ROOT" "$TEMP_ROOT"
export XDG_CACHE_HOME="$CACHE_ROOT/xdg"
export TMPDIR="$TEMP_ROOT"
export TEMP="$TEMP_ROOT"
export TMP="$TEMP_ROOT"

EXTRA_ARGS=""

"$PYTHON" -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --output-dir="$OUTPUT_DIR" \
    --output-filename="termi-word" \
    --include-package="termi_word" \
    --include-package="fsrs" \
    --include-package="sqlalchemy" \
    --include-data-dir="$PROJECT_ROOT/termi_word/styles=termi_word/styles" \
    --mingw64 \
    --nofollow-import-to=termi_word.tests \
    --nofollow-import-to=pytest \
    --nofollow-import-to=openai \
    --nofollow-import-to=pydantic \
    --nofollow-import-to=httpx \
    --nofollow-import-to=requests \
    --nofollow-import-to=urllib3 \
    --nofollow-import-to=langchain \
    --nofollow-import-to=langchain_core \
    --nofollow-import-to=langchain_community \
    --nofollow-import-to=langchain_openai \
    --nofollow-import-to=langchain_ollama \
    --nofollow-import-to=langchain_text_splitters \
    --nofollow-import-to=faker \
    $EXTRA_ARGS \
    "$PROJECT_ROOT/run.py"

DIST_DIR="$OUTPUT_DIR/run.dist"
BUILD_EXE="$DIST_DIR/termi-word"
if [ ! -f "$BUILD_EXE" ] && [ -f "$BUILD_EXE.exe" ]; then
    BUILD_EXE="$BUILD_EXE.exe"
fi

if [ ! -f "$BUILD_EXE" ]; then
    echo "Built executable not found: $BUILD_EXE" >&2
    exit 1
fi

echo "Built Standalone: $DIST_DIR"
echo "Executable: $BUILD_EXE"
