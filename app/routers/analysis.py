"""
分析相关 API 路由。

端点：
- POST /api/analyze     — 分析论文
- POST /api/reports     — 保存报告
- GET  /api/reports     — 列表
- GET  /api/reports/{id}— 详情
"""
import logging
import traceback

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.schemas import AnalyzeRequest, SaveReportRequest
from app.services.parser import validate_content, ParseError
from app.services.analyzer import analyze_paper, AnalysisError
from app.services.storage import save_report, list_reports, get_report, update_report, delete_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze")
async def api_analyze(request: AnalyzeRequest):
    """
    分析一篇论文。

    输入：论文 markdown 内容 + 选中的分析维度
    输出：结构化分析报告
    """
    logger.info(f"收到分析请求: {len(request.content)} 字符, "
                f"{len(request.dimensions)} 个维度: "
                f"{[d.label for d in request.dimensions]}")

    # 1. 校验内容
    try:
        validation = validate_content(request.content)
    except ParseError as e:
        logger.warning(f"内容校验失败: {e.error_type} - {e.message}")
        raise HTTPException(status_code=400, detail={
            "error_type": e.error_type,
            "message": e.message,
        })

    # 2. 调用 AI 分析
    try:
        result = analyze_paper(request.content, request.dimensions)
    except AnalysisError as e:
        logger.error(f"AI 分析失败: {e.error_type} - {e.message}")
        raise HTTPException(status_code=500, detail={
            "error_type": e.error_type,
            "message": e.message,
        })
    except Exception as e:
        logger.error(f"未知错误: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail={
            "error_type": "unknown_error",
            "message": f"分析过程发生未知错误: {e}",
        })

    # 3. 返回结果
    logger.info(f"分析成功: 标题={result['paper_title']}, "
                f"段落数={len(result['sections'])}")
    return {
        "paper_title": result["paper_title"],
        "sections": result["sections"],
        "raw_content_length": result["raw_content_length"],
        "dimensions_used": result.get("dimensions_used", []),
        "warnings": validation.get("warnings", []),
    }


@router.post("/reports")
async def api_save_report(request: SaveReportRequest):
    """保存分析报告"""
    try:
        sections_dicts = [
            {"dimension": s.dimension, "content": s.content}
            for s in request.sections
        ]
        report_id = save_report(
            paper_title=request.paper_title,
            original_content=request.original_content,
            sections=sections_dicts,
            dimensions=request.dimensions,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error_type": "storage_error",
            "message": f"保存失败: {e}",
        })

    return {"id": report_id, "saved": True}


@router.get("/reports")
async def api_list_reports():
    """获取所有已保存的报告列表"""
    reports = list_reports()
    return {
        "reports": [
            {
                "id": r.id,
                "paper_title": r.paper_title,
                "dimensions": r.dimensions,
                "created_at": r.created_at,
            }
            for r in reports
        ]
    }


@router.get("/reports/{report_id}")
async def api_get_report(report_id: str):
    """获取单个报告详情"""
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail={
            "error_type": "not_found",
            "message": f"报告 {report_id} 不存在",
        })

    return {
        "id": report.id,
        "paper_title": report.paper_title,
        "sections": [
            {"dimension": s.dimension, "content": s.content}
            for s in report.sections
        ],
        "original_content": report.original_content,
        "created_at": report.created_at,
    }


@router.put("/reports/{report_id}")
async def api_update_report(report_id: str, request: SaveReportRequest):
    """更新已保存的报告 sections"""
    if not update_report(report_id, [
        {"dimension": s.dimension, "content": s.content}
        for s in request.sections
    ]):
        raise HTTPException(status_code=404, detail={
            "error_type": "not_found",
            "message": f"报告 {report_id} 不存在",
        })
    return {"id": report_id, "updated": True}


@router.delete("/reports/{report_id}")
async def api_delete_report(report_id: str):
    """删除报告"""
    if not delete_report(report_id):
        raise HTTPException(status_code=404, detail={
            "error_type": "not_found",
            "message": f"报告 {report_id} 不存在",
        })
    return {"id": report_id, "deleted": True}
