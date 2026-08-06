"""
论文分析引擎 —— 整个产品的核心。

职责：
1. 根据用户指定的维度构建分析 prompt
2. 调用 DeepSeek API 生成结构化分析
3. 解析 API 返回的 JSON 结果
"""
import json
import re
import logging

from openai import OpenAI
from json_repair import repair_json

from app.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    DEEPSEEK_PRO_MODEL, DEEPSEEK_FLASH_MODEL,
    FLASH_DIMENSION_KEYS,
)
from app.models.schemas import DimensionSpec
from app.models.templates import get_dimension_by_key, ANALYSIS_DIMENSIONS


class AnalysisError(Exception):
    """分析错误"""

    def __init__(self, message: str, error_type: str = "analysis_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


def _build_system_prompt(dimensions: list[DimensionSpec]) -> str:
    """构建系统指令 prompt，维度由前端直接传入（含用户编辑后的内容）"""
    # 构建维度描述列表
    dim_lines = []
    for i, d in enumerate(dimensions, 1):
        desc = d.description.strip() if d.description.strip() else f"请从「{d.label}」的角度分析这篇论文"
        dim_lines.append(f"{i}. **{d.label}**：{desc}")

    dim_desc = "\n".join(dim_lines)
    labels = [d.label for d in dimensions]

    return f"""你是一个严谨的学术论文分析助手。用户会提供一篇学术论文的 markdown 全文，请你按照以下维度对论文进行结构化分析。

## 分析维度

{dim_desc}

## 输出要求

1. 先提取论文的准确标题
2. **每个维度都必须生成不少于 300 字的深度分析，无论选择了多少个维度，单个维度的分析深度不应降低；具体结构和格式遵循各维度的描述要求**
3. **分析必须严格基于论文原文内容，不得编造任何论文中不存在的信息**
4. 如果论文中没有涉及某个维度的足够信息，请在该维度的分析中明确说明"论文中未充分涉及该维度"
5. **提到任何前人研究、理论或观点时，必须注明作者和发表年份**（如"Jacobs(1961)""Gehl(2010)"），不得笼统提及"传统理论""已有研究"而不标注来源
6. 使用学术、客观的语言

## 输出格式

你必须严格按照以下 JSON 格式输出，不要输出任何 JSON 之外的内容。各维度的 content 字段内可以使用 \n 换行来分隔不同段落，以提升可读性：

```json
{{
  "paper_title": "论文完整标题",
  "sections": [
    {", ".join(f'{{"dimension": "{label}", "content": "分析内容..."}}' for label in labels)}
  ]
}}
```

现在请分析以下论文："""


def _parse_analysis_response(raw_text: str) -> dict:
    """
    解析 DeepSeek API 返回的原始文本，提取 JSON。

    处理多种情况：
    - 标准 JSON 代码块包裹
    - 纯 JSON 文本
    - JSON 前后有额外文本
    """
    # 检测 HTML 错误页面（服务端异常，非模型输出）
    stripped = raw_text.strip()
    if stripped.startswith("<!DOCTYPE") or stripped.startswith("<html"):
        raise AnalysisError(
            "API 服务返回了错误页面，可能是服务端异常或网络波动，请稍后重试。",
            "html_response",
        )

    json_match = re.search(r"```json\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        code_match = re.search(r"```\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
        if code_match:
            json_str = code_match.group(1).strip()
        else:
            brace_start = raw_text.find("{")
            brace_end = raw_text.rfind("}")
            if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                json_str = raw_text[brace_start:brace_end + 1]
            else:
                raise AnalysisError(
                    "无法从 API 响应中提取 JSON 结构。"
                    f"原始响应前 500 字符: {raw_text[:500]}",
                    "json_parse_error",
                )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # JSON 损坏时尝试自动修复（处理未转义引号、缺少逗号等常见问题）
        try:
            repaired = repair_json(json_str)
            data = json.loads(repaired)
            logging.getLogger(__name__).warning("JSON 格式已自动修复")
        except Exception:
            raise AnalysisError(
                f"API 返回的 JSON 格式无效且无法自动修复。"
                f"原始内容前 500 字符: {json_str[:500]}",
                "json_parse_error",
            )

    if "paper_title" not in data:
        raise AnalysisError("API 响应缺少 paper_title 字段", "missing_fields")
    if "sections" not in data or not isinstance(data["sections"], list) or len(data["sections"]) == 0:
        raise AnalysisError("API 响应缺少 sections 字段或格式不正确", "missing_fields")

    return data


def _find_source_prefix(claim_text: str, original_content: str, prefix_len: int = 10) -> str:
    """
    在原文中搜索与论点最匹配的段落，返回其前 N 个字符。

    算法：将原文按段落分割，对每条论点计算与各段落的字符重叠度，
    取重叠度最高的段落的前 N 个字符作为原文出处。
    如果找不到有效匹配（重叠度过低），返回空字符串。
    """
    paragraphs = [p.strip() for p in original_content.split("\n") if p.strip()]
    if not paragraphs:
        return ""

    # 去掉 markdown 标记，提取纯文本用于匹配
    claim_chars = set(claim_text.replace(" ", "").replace("\n", ""))

    best_para = None
    best_overlap = 0
    for para in paragraphs:
        para_clean = para.replace(" ", "").replace("\n", "")
        if not para_clean:
            continue
        para_chars = set(para_clean)
        overlap = len(claim_chars & para_chars)
        if overlap > best_overlap:
            best_overlap = overlap
            best_para = para_clean

    # 阈值：至少要有 3 个共同字符才算有效匹配
    if best_para is None or best_overlap < 3:
        return ""

    # 返回前 N 个字符（跳过 # 等 markdown 标记）
    clean = best_para.lstrip("#").strip()
    if len(clean) <= prefix_len:
        return clean
    return clean[:prefix_len]


def _enrich_citable_points(sections: list[dict], original_content: str) -> list[dict]:
    """
    对"可引用论点"段落进行后处理。

    - 如果模型已按结构化格式输出（含"原文出处"或"原文定位"），
      说明维度的提示词已要求模型自行摘录原文，跳过二次处理。
    - 否则按旧版编号列表格式进行原文匹配和格式化（向后兼容）。
    """
    import re

    for section in sections:
        if section.get("dimension") != "可引用论点":
            continue

        raw = section["content"]

        # 模型已按结构化格式输出，跳过后处理
        if "原文出处" in raw or "原文定位" in raw:
            continue

        # 旧版格式：按编号拆分为独立论点
        claim_parts = re.split(r"\n(?=\d+\.\s)", raw.strip())
        if len(claim_parts) <= 1:
            claim_parts = re.split(r"\n(?=\d+[\.\、\)]\s*)", raw.strip())

        enriched_parts = []
        for part in claim_parts:
            part = part.strip()
            if not part:
                continue
            claim_body = re.sub(r"^\d+[\.\、\)]\s*", "", part).strip()
            if not claim_body:
                enriched_parts.append(part)
                continue

            prefix = _find_source_prefix(claim_body, original_content)
            if prefix:
                enriched = f"{claim_body}（原文出处：\"{prefix}…\"）"
            else:
                enriched = f"{claim_body}（原文出处：未定位到原文段落）"
            enriched_parts.append(enriched)

        if enriched_parts:
            section["content"] = "\n\n".join(enriched_parts)

    return sections


def _get_dimension_key(dimension: DimensionSpec) -> str | None:
    """根据维度标签反查 key（用于判断是否属于 Flash 维度组）"""
    label_to_key = {d["label"]: d["key"] for d in ANALYSIS_DIMENSIONS}
    return label_to_key.get(dimension.label)


def _call_api(content: str, dimensions: list[DimensionSpec], model: str,
              retry: bool = True, thinking: bool = False) -> dict:
    """调用 DeepSeek API 分析论文（处理一组维度），JSON 解析失败时自动重试一次"""
    logger = logging.getLogger(__name__)
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    system_prompt = _build_system_prompt(dimensions)

    extra = {}
    if thinking:
        extra["extra_body"] = {"thinking": {"type": "enabled"}}

    def _do_call():
        try:
            return client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                temperature=0,
                max_tokens=16384,
                **extra,
            )
        except Exception as e:
            raise AnalysisError(f"调用 {model} 失败: {e}", "api_call_error")

    response = _do_call()
    raw_text = response.choices[0].message.content or ""

    try:
        result = _parse_analysis_response(raw_text)
    except AnalysisError as e:
        if retry and e.error_type == "json_parse_error":
            # JSON 格式损坏时重试一次
            logger.warning(f"{model} JSON 解析失败，重试中...")
            response = _do_call()
            raw_text = response.choices[0].message.content or ""
            result = _parse_analysis_response(raw_text)
        else:
            raise

    finish_reason = response.choices[0].finish_reason
    if finish_reason == "length":
        raise AnalysisError(
            f"分析结果可能不完整（{model} 输出被截断）。请尝试减少分析维度或分段提交论文。",
            "response_truncated",
        )

    return result


def analyze_paper(content: str, dimensions: list[DimensionSpec]) -> dict:
    """
    分析论文并返回结构化结果。

    根据维度类型分配模型：
    - 研究问题、局限性、方法论 → Flash（快速、低成本）
    - 创新点、可引用论点、研究结论、自定义维度 → Pro（深度推理）
    """
    if not DEEPSEEK_API_KEY:
        raise AnalysisError(
            "DeepSeek API Key 未配置。请在 .env 文件中设置 DEEPSEEK_API_KEY。",
            "no_api_key",
        )

    # 拆分维度：Flash 组 vs Pro 组（保持原始顺序）
    flash_dims = []
    pro_dims = []
    flash_indices = []
    pro_indices = []

    for i, d in enumerate(dimensions):
        key = _get_dimension_key(d)
        if key and key in FLASH_DIMENSION_KEYS:
            flash_dims.append(d)
            flash_indices.append(i)
        else:
            pro_dims.append(d)
            pro_indices.append(i)

    # 分别调用
    results_by_index = {}  # index → section dict
    errors = []
    paper_title = None

    if flash_dims:
        try:
            flash_result = _call_api(content, flash_dims, DEEPSEEK_FLASH_MODEL, thinking=False)
            paper_title = flash_result["paper_title"]
            for j, idx in enumerate(flash_indices):
                results_by_index[idx] = flash_result["sections"][j]
        except AnalysisError as e:
            errors.append(str(e.message))

    if pro_dims:
        try:
            pro_result = _call_api(content, pro_dims, DEEPSEEK_PRO_MODEL, thinking=True)
            paper_title = pro_result["paper_title"]  # Pro 标题优先级更高（后覆盖）
            for j, idx in enumerate(pro_indices):
                results_by_index[idx] = pro_result["sections"][j]
        except AnalysisError as e:
            errors.append(str(e.message))

    if not results_by_index:
        raise AnalysisError(
            "所有维度分析均失败: " + "; ".join(errors),
            "all_models_failed",
        )

    if not paper_title:
        paper_title = "分析报告"

    # 按原始顺序合并 sections
    merged_sections = [results_by_index[i] for i in sorted(results_by_index.keys())]

    # 后处理：为"可引用论点"自动补充原文出处
    merged_sections = _enrich_citable_points(merged_sections, content)

    return {
        "paper_title": paper_title,
        "sections": merged_sections,
        "raw_content_length": len(content),
        "dimensions_used": [d.label for d in dimensions],
    }
