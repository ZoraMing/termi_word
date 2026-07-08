from __future__ import annotations

import unicodedata

from rich.text import Text

from termi_word.config import MAX_PANEL_HEIGHT, MIN_PANEL_HEIGHT, PANEL_WIDTH


def display_width(text: str) -> int:
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def truncate_display(text: str, width: int = PANEL_WIDTH) -> str:
    if display_width(text) <= width:
        return text
    result = ""
    used = 0
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if used + char_width > width - 3:
            break
        result += char
        used += char_width
    return result + "..."


def pad_display(text: str, width: int = PANEL_WIDTH) -> str:
    return text + " " * max(0, width - display_width(text))


def panel_height(terminal_height: int) -> int:
    return max(MIN_PANEL_HEIGHT, min(MAX_PANEL_HEIGHT, terminal_height))


def scroll_window(lines: list[str], height: int, offset: int) -> list[str]:
    if height <= 0:
        return []
    offset = max(0, min(offset, max(0, len(lines) - height)))
    visible = lines[offset : offset + height]
    while len(visible) < height:
        visible.append("")
    return visible


PanelLine = str | Text


def append_line(text: Text, line: PanelLine) -> None:
    if isinstance(line, Text):
        text.append_text(line)
    else:
        text.append(truncate_display(line))


def text_panel(title: str, lines: list[PanelLine], footer: str, height: int, status: str = "") -> Text:
    body_height = max(1, height - 2)
    visible = scroll_window(lines, body_height, 0)
    text = Text()
    head = f"{title:<48}{status}".rstrip()
    text.append(truncate_display(head), style="bold")
    text.append("\n")
    for line in visible[:-1]:
        append_line(text, line)
        text.append("\n")
    if visible:
        append_line(text, visible[-1])
        text.append("\n")
    text.append(truncate_display(footer), style="dim")
    return text


def rating_label(rating: int) -> str:
    return {1: "陌生", 2: "熟悉", 3: "记得", 4: "掌握"}.get(rating, "未评分")
