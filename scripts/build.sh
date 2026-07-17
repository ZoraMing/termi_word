#!/usr/bin/env sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON:-}"

if [ -z "$PYTHON" ]; then
    if [ -n "${VIRTUAL_ENV:-}" ] || [ -n "${CONDA_PREFIX:-}" ]; then
        PYTHON="python"
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

"$PYTHON" -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --output-dir="$OUTPUT_DIR" \
    --output-filename="termi-word" \
    --include-package="termi_word" \
    --include-data-dir="$PROJECT_ROOT/termi_word/styles=termi_word/styles" \
    --mingw64 \
    --lto=yes \
    --nofollow-import-to=pytest \
    --nofollow-import-to=openai \
    --nofollow-import-to=pydantic \
    --nofollow-import-to=httpx \
    --nofollow-import-to=requests \
    --nofollow-import-to=urllib3 \
    --nofollow-import-to=anyio \
    "$PROJECT_ROOT/termi_word/__main__.py"

DIST_DIR="$(find "$OUTPUT_DIR" -maxdepth 1 -type d -name "*.dist" -print | sort | tail -n 1)"
if [ -z "$DIST_DIR" ]; then
    echo "Nuitka dist directory not found in $OUTPUT_DIR" >&2
    exit 1
fi

IMPORTS_DIR="$DIST_DIR/data/imports"
mkdir -p "$IMPORTS_DIR"

if [ -d "$PROJECT_ROOT/data" ]; then
    find "$PROJECT_ROOT/data" -maxdepth 1 -type f -name "*.csv" -exec cp -f {} "$IMPORTS_DIR" \;
fi

echo "Built: $DIST_DIR"
echo "External import directory: $IMPORTS_DIR"
echo "Package workspace: $PACKAGE_ROOT"
