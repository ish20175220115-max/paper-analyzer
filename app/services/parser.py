"""
Markdown 论文解析与校验。
"""
from app.config import MIN_CONTENT_LENGTH, MAX_CONTENT_LENGTH


class ParseError(Exception):
    """解析错误"""

    def __init__(self, message: str, error_type: str = "parse_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


def validate_content(content: str) -> dict:
    """
    校验论文内容并返回元信息。

    返回:
        {"valid": bool, "length": int, "has_title": bool, "error": str | None,
         "warnings": list[str]}
    """
    warnings = []

    # 去除首尾空白
    content = content.strip()

    if not content:
        raise ParseError("论文内容不能为空", "empty_content")

    if len(content) < MIN_CONTENT_LENGTH:
        raise ParseError(
            f"论文内容过短（{len(content)} 字符），最少需要 {MIN_CONTENT_LENGTH} 字符。"
            f"请确认你粘贴的是完整的论文正文。",
            "content_too_short",
        )

    if len(content) > MAX_CONTENT_LENGTH:
        raise ParseError(
            f"论文内容过长（{len(content)} 字符），当前版本最多支持 {MAX_CONTENT_LENGTH} 字符。"
            f"请尝试截取论文的核心章节（引言、方法论、结论）进行分析。",
            "content_too_long",
        )

    # 检查是否有标题（以 # 开头）
    has_title = any(line.strip().startswith("#") for line in content.split("\n") if line.strip())

    if not has_title:
        warnings.append("未检测到 markdown 标题（以 # 开头），可能影响标题提取准确性。")

    # 检查基本结构
    lines = content.split("\n")
    non_empty_lines = [l for l in lines if l.strip()]
    has_paragraphs = len(non_empty_lines) >= 5

    if not has_paragraphs:
        warnings.append("论文内容段落过少，可能不是完整的论文格式。")

    return {
        "valid": True,
        "length": len(content),
        "has_title": has_title,
        "has_paragraphs": has_paragraphs,
        "error": None,
        "warnings": warnings,
    }


def extract_title_from_markdown(content: str) -> str:
    """从 markdown 中尝试提取标题（第一个 # 标题行）"""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return "未命名论文"
