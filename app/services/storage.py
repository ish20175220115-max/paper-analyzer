"""
JSON 文件存储服务。

MVP 阶段使用本地 JSON 文件存储论文和报告，零外部依赖。
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

from app.config import PAPERS_DIR, REPORTS_DIR
from app.models.schemas import ReportDetail, ReportSummary


class StorageError(Exception):
    """存储错误"""
    pass


def _generate_id() -> str:
    """生成唯一 ID"""
    return uuid.uuid4().hex[:12]


def _now_iso() -> str:
    """当前时间 ISO 格式"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_report(paper_title: str, original_content: str,
                sections: list[dict], dimensions: list[str]) -> str:
    """
    保存分析报告和原始论文。

    返回: report_id
    """
    report_id = _generate_id()
    now = _now_iso()

    # 保存原始论文
    paper_path = PAPERS_DIR / f"{report_id}.md"
    try:
        paper_path.write_text(original_content, encoding="utf-8")
    except OSError as e:
        raise StorageError(f"保存论文文件失败: {e}")

    # 保存分析报告
    report_path = REPORTS_DIR / f"{report_id}.json"
    report_data = {
        "id": report_id,
        "paper_title": paper_title,
        "dimensions": dimensions,
        "sections": sections,
        "created_at": now,
    }
    try:
        report_path.write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        # 回滚：删除已保存的论文文件
        paper_path.unlink(missing_ok=True)
        raise StorageError(f"保存报告文件失败: {e}")

    return report_id


def list_reports() -> list[ReportSummary]:
    """列出所有已保存的报告摘要"""
    summaries = []
    if not REPORTS_DIR.exists():
        return summaries

    for report_file in sorted(
        REPORTS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
            summaries.append(ReportSummary(
                id=data["id"],
                paper_title=data["paper_title"],
                dimensions=data.get("dimensions", []),
                created_at=data.get("created_at", "未知"),
            ))
        except (json.JSONDecodeError, KeyError):
            continue

    return summaries


def get_report(report_id: str) -> ReportDetail | None:
    """获取单个报告详情"""
    report_path = REPORTS_DIR / f"{report_id}.json"
    if not report_path.exists():
        return None

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return None

    # 读取原始论文
    paper_path = PAPERS_DIR / f"{report_id}.md"
    original_content = ""
    if paper_path.exists():
        original_content = paper_path.read_text(encoding="utf-8")

    return ReportDetail(
        id=data["id"],
        paper_title=data["paper_title"],
        sections=data.get("sections", []),
        original_content=original_content,
        created_at=data.get("created_at", "未知"),
    )


def update_report(report_id: str, sections: list[dict]) -> bool:
    """更新报告的 sections 内容，保留其他字段不变"""
    report_path = REPORTS_DIR / f"{report_id}.json"
    if not report_path.exists():
        return False

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        data["sections"] = sections
        report_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except (json.JSONDecodeError, KeyError, OSError):
        return False



def delete_report(report_id: str) -> bool:
    """删除报告和对应的论文"""
    report_path = REPORTS_DIR / f"{report_id}.json"
    paper_path = PAPERS_DIR / f"{report_id}.md"

    deleted = False
    if report_path.exists():
        report_path.unlink()
        deleted = True
    if paper_path.exists():
        paper_path.unlink()

    return deleted
