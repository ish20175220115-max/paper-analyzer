"""
页面路由 —— 渲染 Jinja2 模板。
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.models.templates import ANALYSIS_DIMENSIONS

router = APIRouter()

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/", response_class=HTMLResponse)
async def page_index(request: Request):
    """首页：论文列表"""
    return templates.TemplateResponse("index.html", {
        "request": request,
    })


@router.get("/upload", response_class=HTMLResponse)
async def page_upload(request: Request):
    """上传与分析页"""
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "dimensions": ANALYSIS_DIMENSIONS,
    })


@router.get("/report/{report_id}", response_class=HTMLResponse)
async def page_view_report(request: Request, report_id: str):
    """查看已保存的报告"""
    return templates.TemplateResponse("view.html", {
        "request": request,
        "report_id": report_id,
    })
