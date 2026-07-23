"""简易 JSON 转 TermiWord CSV 词表脚本

支持并适配以下 4 种常见的 JSON 输入格式：

【格式 1】标准 JSON 列表 (Array of Objects):
[
    {"w": "abandon", "zh": "vt. 放弃", "us": "/əˈbændən/", "ex": "He abandoned his car."},
    {"w": "ability", "zh": "n. 能力", "us": "/əˈbɪləti/"}
]

【格式 2】字典包裹的列表 (Dict containing word list):
{
    "name": "CET4 词汇表",
    "words": [
        {"word": "abandon", "translation": "vt. 放弃", "phonetic": "/əˈbændən/"}
    ]
}

【格式 3】单词-释义简易字典 (Word-to-Definition Mapping):
{
    "abandon": "vt. 放弃，遗弃",
    "ability": "n. 能力，才能"
}

【格式 4】JSONLines 逐行文件 (Line-delimited JSON):
{"w": "abandon", "zh": "vt. 放弃"}
{"w": "ability", "zh": "n. 能力"}
"""

import csv
import json
import sys
from pathlib import Path

# 自定义 JSON 键名 -> CSV 标准列名的对应关系
# 若你的 JSON 键名不同（如使用 "word" 或 "translation"），在此修改冒号右侧的名字即可：
FIELD_MAP = {
    "w": ["w", "word", "headWord", "name", "spelling"],
    "zh": ["zh", "translation", "tran", "meaning", "cn", "definition"],
    "en": ["en", "english", "definition_en"],
    "us": ["us", "phonetic", "pronunciation", "sound"],
    "c": ["c", "category", "tag", "pos"],
    "core": ["core", "memory", "note", "mnemonic"],
    "ex": ["ex", "example", "sentence"],
    "exz": ["exz", "example_trans", "sentence_trans", "ex_zh"],
}


def get_field_value(item: dict, field_key: str) -> str:
    """按字段优先候选列表提取字符串"""
    candidates = FIELD_MAP.get(field_key, [field_key])
    for key in candidates:
        if key in item and item[key] is not None:
            val = item[key]
            if isinstance(val, list):
                return "；".join(str(v) for v in val).strip()
            return str(val).strip()
    return ""


def parse_json_content(content: str) -> list[dict]:
    """尝试将文本内容解析为统一的单词字典列表"""
    content = content.strip()
    if not content:
        return []

    records = []

    # 1. 尝试标准整体 JSON 解析
    try:
        data = json.loads(content)
        # 【格式 1】标准列表
        if isinstance(data, list):
            for x in data:
                if isinstance(x, dict):
                    records.append(x)
                elif isinstance(x, str):
                    records.append({"w": x})

        # 【格式 2 & 格式 3】字典结构
        elif isinstance(data, dict):
            # 检查是否有 words / data / list / items 包裹列表
            list_key = None
            for k in ["words", "data", "list", "items", "content"]:
                if k in data and isinstance(data[k], list):
                    list_key = k
                    break

            if list_key:
                # 格式 2: {"words": [...]}
                for x in data[list_key]:
                    if isinstance(x, dict):
                        records.append(x)
            else:
                # 格式 3: {"abandon": "vt. 放弃", "ability": "n. 能力"}
                for k, v in data.items():
                    if isinstance(v, str):
                        records.append({"w": k, "zh": v})
                    elif isinstance(v, dict):
                        obj = dict(v)
                        obj.setdefault("w", k)
                        records.append(obj)
        return records
    except Exception:
        pass

    # 2. 尝试【格式 4】JSONLines 逐行解析
    for line in content.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        try:
            obj = json.loads(line_str)
            if isinstance(obj, dict):
                records.append(obj)
        except Exception:
            pass

    return records


def convert_json_to_csv(json_path_str: str, csv_path_str: str = ""):
    json_path = Path(json_path_str)
    if not json_path.exists():
        print(f"错误：找不到 JSON 文件 '{json_path}'")
        return

    # 默认输出保存至 termi_data/imports/<文件名>.csv
    if not csv_path_str:
        csv_path = Path("termi_data/imports") / f"{json_path.stem}.csv"
    else:
        csv_path = Path(csv_path_str)

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(json_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    items = parse_json_content(content)
    if not items:
        print("错误：无法解析有效的 JSON 单词记录")
        return

    fieldnames = ["w", "c", "zh", "en", "us", "core", "ex", "exz"]
    rows = []

    for item in items:
        w_val = get_field_value(item, "w")
        if not w_val:
            continue

        rows.append({
            "w": w_val,
            "c": get_field_value(item, "c"),
            "zh": get_field_value(item, "zh"),
            "en": get_field_value(item, "en"),
            "us": get_field_value(item, "us"),
            "core": get_field_value(item, "core"),
            "ex": get_field_value(item, "ex"),
            "exz": get_field_value(item, "exz"),
        })

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"转换成功！共转换 {len(rows)} 个单词，已保存至: {csv_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else ""
        convert_json_to_csv(input_file, output_file)
    else:
        print("用法: python scripts/convert_json.py <JSON文件路径> [输出CSV路径]")
