"""
AI 产品 Badcase 测试矩阵。

测试框架将 badcase 分为四个层级：
  L1 - 事实性错误（致命）：编造信息、错误归因
  L2 - 理解性偏差（严重）：正确识别但理解偏了
  L3 - 完整性缺失（中等）：遗漏重要内容
  L4 - 风格性不匹配（轻微）：表达方式不佳

每个测试用例包含：
  - 编号: BC-XXX
  - 输入特征
  - 期望行为
  - 实际输出（运行后填写）
  - 错误层级
  - 是否可复现

运行方式：
  python tests/test_badcase.py
"""

import json
import sys
import os
import unittest

# 将项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.parser import validate_content, ParseError
from app.services.analyzer import _parse_analysis_response, _build_system_prompt, AnalysisError
from app.services.storage import save_report, get_report, list_reports, delete_report
from app.models.templates import get_dimension_by_key, ANALYSIS_DIMENSIONS
from app.models.schemas import DimensionSpec


class TestBadcaseMatrix(unittest.TestCase):
    """Badcase 测试矩阵 —— 覆盖边界输入和异常路径"""

    # ===== 第一层：输入校验（parser.py）=====

    def test_BC001_empty_content(self):
        """BC-001: 空内容输入 → 应拒绝"""
        with self.assertRaises(ParseError) as ctx:
            validate_content("")
        self.assertEqual(ctx.exception.error_type, "empty_content")

    def test_BC002_whitespace_only(self):
        """BC-002: 只有空白字符 → 应拒绝"""
        with self.assertRaises(ParseError):
            validate_content("   \n  \n  ")

    def test_BC003_content_too_short(self):
        """BC-003: 内容过短（<200 字符）→ 应拒绝并提示"""
        short_content = "# 标题\n\n这是一个很短的论文。"  # < 200 chars
        with self.assertRaises(ParseError) as ctx:
            validate_content(short_content)
        self.assertEqual(ctx.exception.error_type, "content_too_short")

    def test_BC004_content_too_long(self):
        """BC-004: 内容超长（>200k 字符）→ 应拒绝"""
        huge_content = "x" * 200_001
        with self.assertRaises(ParseError) as ctx:
            validate_content(huge_content)
        self.assertEqual(ctx.exception.error_type, "content_too_long")

    def test_BC005_valid_minimal_content(self):
        """BC-005: 刚好 200 字符的有效内容 → 应通过"""
        content = "# 测试论文\n\n" + "这是一篇测试论文的内容。" * 20  # ~240+ chars
        result = validate_content(content)
        self.assertTrue(result["valid"])
        self.assertGreaterEqual(result["length"], 200)

    def test_BC006_no_markdown_heading(self):
        """BC-006: 无 markdown 标题的内容 → 应通过但有警告"""
        content = "这是一篇没有标题的论文内容。\n\n" + "正文段落。" * 50
        result = validate_content(content)
        self.assertTrue(result["valid"])
        self.assertFalse(result["has_title"])
        self.assertTrue(len(result["warnings"]) > 0)

    def test_BC007_chinese_english_mixed(self):
        """BC-007: 中英混排论文 → 应正常解析"""
        content = "# A Study on Machine Learning 机器学习研究\n\n"
        content += "This paper proposes a novel approach using Transformer architecture.\n\n"
        content += "本文提出了一种基于 Transformer 架构的新方法。实验结果表明..." * 10
        result = validate_content(content)
        self.assertTrue(result["valid"])

    def test_BC008_markdown_with_latex(self):
        """BC-008: 含 LaTeX 公式的 markdown → 应正常解析（公式作为文本保留）"""
        content = "# 数学方法论文\n\n"
        content += "公式如下：$$L = \\frac{1}{N}\\sum_{i=1}^{N} (y_i - \\hat{y}_i)^2$$\n\n"
        content += "正文内容。" * 30
        result = validate_content(content)
        self.assertTrue(result["valid"])

    # ===== 第二层：JSON 解析（analyzer.py）=====

    def test_BC101_valid_json_block(self):
        """BC-101: 标准 ```json``` 代码块包裹 → 应正确解析"""
        raw = '```json\n{"paper_title": "测试", "sections": [{"dimension": "方法论", "content": "内容"}]}\n```'
        result = _parse_analysis_response(raw)
        self.assertEqual(result["paper_title"], "测试")
        self.assertEqual(len(result["sections"]), 1)

    def test_BC102_valid_json_no_wrapper(self):
        """BC-102: 纯 JSON 无代码块 → 应正确解析"""
        raw = '{"paper_title": "测试论文", "sections": [{"dimension": "创新点", "content": "分析"}]}'
        result = _parse_analysis_response(raw)
        self.assertEqual(result["paper_title"], "测试论文")

    def test_BC103_json_with_trailing_text(self):
        """BC-103: JSON 前后有额外文本 → 应提取 JSON 部分"""
        raw = '好的，以下是分析结果：\n```json\n{"paper_title": "T", "sections": [{"dimension": "X", "content": "Y"}]}\n```\n希望对你有帮助！'
        result = _parse_analysis_response(raw)
        self.assertEqual(result["paper_title"], "T")

    def test_BC104_missing_paper_title(self):
        """BC-104: JSON 缺少 paper_title 字段 → 应抛异常"""
        raw = '{"sections": [{"dimension": "A", "content": "B"}]}'
        with self.assertRaises(AnalysisError) as ctx:
            _parse_analysis_response(raw)
        self.assertEqual(ctx.exception.error_type, "missing_fields")

    def test_BC105_missing_sections(self):
        """BC-105: JSON 缺少 sections 字段 → 应抛异常"""
        raw = '{"paper_title": "测试"}'
        with self.assertRaises(AnalysisError) as ctx:
            _parse_analysis_response(raw)
        self.assertEqual(ctx.exception.error_type, "missing_fields")

    def test_BC106_empty_sections(self):
        """BC-106: sections 为空数组 → 应抛异常"""
        raw = '{"paper_title": "测试", "sections": []}'
        with self.assertRaises(AnalysisError):
            _parse_analysis_response(raw)

    def test_BC107_invalid_json(self):
        """BC-107: 完全不是 JSON → 应抛异常"""
        raw = "这不是 JSON，只是一段普通文本。"
        with self.assertRaises(AnalysisError) as ctx:
            _parse_analysis_response(raw)
        self.assertEqual(ctx.exception.error_type, "json_parse_error")

    def test_BC108_malformed_json(self):
        """BC-108: JSON 格式损坏（缺少括号）→ 应抛异常"""
        raw = '{"paper_title": "测试", "sections": [{"dimension": "A"'
        with self.assertRaises(AnalysisError):
            _parse_analysis_response(raw)

    # ===== 第三层：Prompt 构建 =====

    def test_BC201_single_dimension_prompt(self):
        """BC-201: 选择单个维度 → prompt 应包含该维度"""
        dims = [DimensionSpec(label="研究问题", description="论文核心问题是什么？")]
        prompt = _build_system_prompt(dims)
        self.assertIn("研究问题", prompt)
        self.assertIn("核心问题", prompt)

    def test_BC202_all_dimensions_prompt(self):
        """BC-202: 全选维度 → prompt 应包含所有维度"""
        dims = [DimensionSpec(label=d["label"], description=d["description"]) for d in ANALYSIS_DIMENSIONS]
        prompt = _build_system_prompt(dims)
        self.assertIn("研究问题", prompt)
        self.assertIn("方法论", prompt)
        self.assertIn("创新点", prompt)
        self.assertIn("局限性", prompt)
        self.assertIn("可引用论点", prompt)

    def test_BC203_custom_edited_dimension(self):
        """BC-203: 用户编辑过的维度 → prompt 应使用编辑后的值"""
        dims = [DimensionSpec(label="我的自定义维度", description="关注实验部分的数据质量")]
        prompt = _build_system_prompt(dims)
        self.assertIn("我的自定义维度", prompt)
        self.assertIn("实验部分的数据质量", prompt)

    # ===== 第四层：存储 =====

    def test_BC301_save_and_retrieve(self):
        """BC-301: 保存报告后能正确读取"""
        rid = save_report(
            paper_title="存储测试论文",
            original_content="# 测试\n\n内容。",
            sections=[{"dimension": "创新点", "content": "这是一项创新。"}],
            dimensions=["innovation"],
        )
        report = get_report(rid)
        self.assertIsNotNone(report)
        self.assertEqual(report.paper_title, "存储测试论文")
        self.assertEqual(len(report.sections), 1)

        # 清理
        delete_report(rid)

    def test_BC302_get_nonexistent_report(self):
        """BC-302: 读取不存在的报告 → 返回 None"""
        report = get_report("nonexistent_id_12345")
        self.assertIsNone(report)

    def test_BC303_list_empty(self):
        """BC-303: 空数据库列表 → 返回空数组"""
        reports = list_reports()
        # 不做严格断言，因为可能有其他测试残留
        self.assertIsInstance(reports, list)

    # ===== 第五层：模板定义 =====

    def test_BC401_dimension_lookup(self):
        """BC-401: 根据 key 查维度 → 正确返回"""
        dim = get_dimension_by_key("methodology")
        self.assertIsNotNone(dim)
        self.assertEqual(dim["label"], "方法论")

    def test_BC402_unknown_dimension_key(self):
        """BC-402: 查询不存在的维度 key → 返回 None"""
        dim = get_dimension_by_key("nonexistent_key")
        self.assertIsNone(dim)


class TestBadcaseReport(unittest.TestCase):
    """
    生成 Badcase 测试报告。

    在实际运行中，你需要手动运行完整链路来测试真正的 AI 输出质量。
    下面的测试只覆盖可自动化的边界情况。
    """

    def test_generate_badcase_report(self):
        """生成 badcase 测试报告模板"""
        report = {
            "test_date": "待填写",
            "total_cases": 0,
            "passed": 0,
            "failed": 0,
            "manual_cases": [
                {
                    "id": "BC-M001",
                    "name": "幻觉引用测试",
                    "description": "输入一篇不存在的论文标题，观察系统是否编造分析",
                    "input": "构造一篇虚构论文的 markdown",
                    "expected": "系统应拒绝分析或明确说明论文信息不足",
                    "actual": "待测试",
                    "level": "L1-事实性错误",
                    "reproducible": "待确认",
                },
                {
                    "id": "BC-M002",
                    "name": "跨学科混淆测试",
                    "description": "输入计算语言学论文但选择纯人文模板",
                    "input": "一篇 NLP 论文 + 仅选「可引用论点」",
                    "expected": "分析内容应与论文实际内容匹配",
                    "actual": "待测试",
                    "level": "L2-理解性偏差",
                    "reproducible": "待确认",
                },
                {
                    "id": "BC-M003",
                    "name": "公式/图表丢失测试",
                    "description": "输入含大量 LaTeX 公式的论文",
                    "input": "含 $$ 公式块的 markdown 论文",
                    "expected": "公式在分析中被引用而非忽略",
                    "actual": "待测试",
                    "level": "L3-完整性缺失",
                    "reproducible": "待确认",
                },
                {
                    "id": "BC-M004",
                    "name": "长文截断测试",
                    "description": "输入 5 万字以上的博士论文",
                    "input": "一篇完整博士论文 markdown",
                    "expected": "全文覆盖或明确说明聚焦范围",
                    "actual": "待测试",
                    "level": "L3-完整性缺失",
                    "reproducible": "待确认",
                },
                {
                    "id": "BC-M005",
                    "name": "综述论文识别测试",
                    "description": "输入综述论文而非原创研究",
                    "input": "一篇文献综述 markdown",
                    "expected": "不应将综述当作原创研究分析其方法论",
                    "actual": "待测试",
                    "level": "L2-理解性偏差",
                    "reproducible": "待确认",
                },
                {
                    "id": "BC-M006",
                    "name": "一致性测试",
                    "description": "同一篇论文跑 3 次",
                    "input": "同一篇论文连续分析 3 次",
                    "expected": "核心结论应一致",
                    "actual": "待测试",
                    "level": "L2-理解性偏差",
                    "reproducible": "待确认",
                },
                {
                    "id": "BC-M007",
                    "name": "格式破坏测试",
                    "description": "损坏的 markdown 结构",
                    "input": "标题层级混乱、嵌套错误的 markdown",
                    "expected": "不崩溃，能给出部分分析",
                    "actual": "待测试",
                    "level": "L3-完整性缺失",
                    "reproducible": "待确认",
                },
                {
                    "id": "BC-M008",
                    "name": "中英混排术语测试",
                    "description": "中文论文大量英文术语",
                    "input": "中文学术论文含大量英文专业术语",
                    "expected": "关键术语不被翻译错误",
                    "actual": "待测试",
                    "level": "L2-理解性偏差",
                    "reproducible": "待确认",
                },
            ],
        }

        # 输出报告
        print("\n" + "=" * 60)
        print("  AI 产品 Badcase 测试报告")
        print("=" * 60)
        print(f"\n自动测试用例数: {report['total_cases']}")
        print(f"需手动测试用例数: {len(report['manual_cases'])}")
        print(f"\n手动测试清单:")
        for case in report["manual_cases"]:
            print(f"  [{case['id']}] {case['name']} ({case['level']})")
            print(f"       描述: {case['description']}")
            print(f"       期望: {case['expected']}")
            print()

        # 保存报告
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "badcase_report.json"
        )
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已保存至: {report_path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
