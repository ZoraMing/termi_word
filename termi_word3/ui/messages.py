"""将结构化业务结果转换为用户可见的中文文案。"""
from __future__ import annotations

from termi_word3.domain.results import ImportResult, SpellingResult, StudyActionResult


def format_import_result(result: ImportResult) -> str:
    """格式化导入结果文案"""
    if result.source_missing:
        return f"找不到词表：{result.source_missing}"
    if result.missing_fields:
        return f"同步失败！词表字段缺失：{', '.join(result.missing_fields)}。请先绑定字段后再试。"

    parts: list[str] = []
    if result.imported:
        parts.append(f"已导入 {result.imported} 个单词")
    if result.updated:
        parts.append(f"更新 {result.updated} 个单词")
    if result.skipped and not parts:
        return "词表已就绪"
    if result.skipped:
        parts.append(f"跳过 {result.skipped} 行")
    return "，".join(parts) if parts else "没有可导入的单词"


def format_spelling_result(result: SpellingResult) -> str:
    """格式化拼写结果文案"""
    if result.is_correct:
        return "太棒了，拼写正确！"
    return f"拼写错误。正确拼写应为: {result.expected}"


def format_study_action_result(result: StudyActionResult) -> str:
    """格式化学习行为评分文案"""
    return result.msg
