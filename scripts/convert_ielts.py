import json
import csv
from pathlib import Path

# 获取项目根目录和文件路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = PROJECT_ROOT / "data" / "IELTSluan_2.json"
CSV_PATH = PROJECT_ROOT / "data" / "IELTSluan_2.csv"

def convert():
    if not JSON_PATH.exists():
        print(f"错误: 找不到雅思词包 JSON 文件：{JSON_PATH}")
        return

    csv_rows = []
    
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception as e:
                print(f"第 {idx} 行解析 JSON 出错: {e}")
                continue
            
            # 提取 headWord 并去首尾空格
            w = item.get("headWord", "").strip()
            if not w:
                continue
                
            content_word = item.get("content", {}).get("word", {})
            word_content = content_word.get("content", {})
            
            # 1. 英音音标与美音音标
            c = word_content.get("ukphone", "").strip()
            us = word_content.get("usphone", "").strip()
            
            # 2. 中文释义与英文释义拼接
            trans = word_content.get("trans", [])
            zh_parts = []
            en_parts = []
            for t in trans:
                pos = t.get("pos", "").strip()
                tranCn = t.get("tranCn", "").strip()
                tranOther = t.get("tranOther", "").strip()
                
                # 中文释义格式：词性. 释义
                if pos:
                    zh_parts.append(f"{pos}. {tranCn}")
                else:
                    zh_parts.append(tranCn)
                
                # 英文释义格式：词性. 英文定义
                if tranOther:
                    if pos:
                        en_parts.append(f"{pos}. {tranOther}")
                    else:
                        en_parts.append(tranOther)
            
            zh = "；".join(zh_parts)
            en = "；".join(en_parts)
            
            # 3. 核心助记（记忆方法）与核心短语
            core_parts = []
            rem = word_content.get("remMethod", {})
            if rem and rem.get("val"):
                core_parts.append(f"【记忆】{rem['val'].strip()}")
            
            phrases = word_content.get("phrase", {}).get("phrases", [])
            if phrases:
                ph_list = []
                for p in phrases[:3]: # 只取前 3 个短语
                    pContent = p.get("pContent", "").strip()
                    pCn = p.get("pCn", "").strip()
                    if pContent:
                        ph_list.append(f"{pContent} ({pCn})")
                if ph_list:
                    core_parts.append(f"【短语】{', '.join(ph_list)}")
            
            core = " | ".join(core_parts)
            
            # 4. 英文例句与中文翻译（只取第一个最具代表性的例句）
            sentences = word_content.get("sentence", {}).get("sentences", [])
            ex = ""
            exz = ""
            if sentences:
                ex = sentences[0].get("sContent", "").strip()
                exz = sentences[0].get("sCn", "").strip()
                
            csv_rows.append({
                "w": w,
                "c": c,
                "zh": zh,
                "en": en,
                "us": us,
                "core": core,
                "ex": ex,
                "exz": exz
            })

    print(f"数据解析完成。共提取到 {len(csv_rows)} 个有效单词。")
    print(f"正在写入 CSV 文件到：{CSV_PATH}...")
    
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        # 定义与 Word 模型表结构一致的列名
        writer = csv.DictWriter(f, fieldnames=["w", "c", "zh", "en", "us", "core", "ex", "exz"])
        writer.writeheader()
        writer.writerows(csv_rows)
        
    print("雅思词包 CSV 文件生成成功！")

if __name__ == "__main__":
    convert()
