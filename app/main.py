"""
个人论文分析管理智能体 —— FastAPI 入口。

启动方式：
    uvicorn app.main:app --reload --port 8000
"""
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR
from app.routers import analysis, pages

# 配置日志，方便排查问题
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title="个人论文分析管理智能体",
    description="输入 markdown 格式论文，AI 自动生成结构化分析报告",
    version="0.1.0",
)

# 注册路由
app.include_router(analysis.router)
app.include_router(pages.router)

# 静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "0.1.0"}
