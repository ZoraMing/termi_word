#!/usr/bin/env sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON:-}"

# 检测 Python 可执行文件
if [ -z "$PYTHON" ]; then
    if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
        PYTHON="$PROJECT_ROOT/.venv/bin/python"
    elif [ -x "$PROJECT_ROOT/.venv_wsl/bin/python" ]; then
        PYTHON="$PROJECT_ROOT/.venv_wsl/bin/python"
    elif [ -x "$PROJECT_ROOT/.venv_linux/bin/python" ]; then
        PYTHON="$PROJECT_ROOT/.venv_linux/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON="python"
    else
        PYTHON="python3"
    fi
fi


PACKAGE_ROOT="${PACKAGE_ROOT:-$PROJECT_ROOT}"
OUTPUT_DIR="$PACKAGE_ROOT/output"
CACHE_ROOT="$PROJECT_ROOT/cache"
TEMP_ROOT="$PROJECT_ROOT/temp"
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
    --nofollow-import-to=faker \
    $EXTRA_ARGS \
    "$PROJECT_ROOT/termi_word/__main__.py"

DIST_DIR="$OUTPUT_DIR/dist"
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

if [ "$(uname)" = "Darwin" ]; then
    ARCHIVE_PATH="$OUTPUT_DIR/termi_word_mac.tar.gz"
else
    ARCHIVE_PATH="$OUTPUT_DIR/termi_word_linux.tar.gz"
fi

echo "Compressing into $ARCHIVE_PATH ..."
tar -czvf "$ARCHIVE_PATH" -C "$DIST_DIR" .
echo "Package compressed successfully: $ARCHIVE_PATH"


