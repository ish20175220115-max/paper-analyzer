"""
个人论文分析管理智能体 —— FastAPI 入口。

启动方式：
    uvicorn app.main:app --reload --port 8000
"""
import json
import logging
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, DATA_DIR, ACCESS_KEY
from app.routers import analysis, pages

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# 每日调用上限
DAILY_LIMIT = 50
LIMIT_FILE = DATA_DIR / "usage.json"

app = FastAPI(
    title="个人论文分析管理智能体",
    description="输入 markdown 格式论文，AI 自动生成结构化分析报告",
    version="0.1.0",
)


# 访问密钥中间件（ACCESS_KEY 为空则不启用）
@app.middleware("http")
async def access_guard(request: Request, call_next):
    if ACCESS_KEY and request.url.path != "/health":
        if request.query_params.get("key") != ACCESS_KEY:
            raise HTTPException(status_code=403, detail={
                "message": "访问被拒绝。请在链接后添加 ?key=你的密钥",
            })
    return await call_next(request)


# 简易每日调用限流中间件
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path == "/api/analyze" and request.method == "POST":
        today = str(date.today())
        try:
            usage = json.loads(LIMIT_FILE.read_text()) if LIMIT_FILE.exists() else {}
        except (json.JSONDecodeError, OSError):
            usage = {}
        count = usage.get(today, 0)
        if count >= DAILY_LIMIT:
            raise HTTPException(status_code=429, detail={
                "error_type": "rate_limited",
                "message": f"今日分析次数已达上限（{DAILY_LIMIT}次），请明天再试。",
            })
        usage[today] = count + 1
        LIMIT_FILE.write_text(json.dumps(usage))
    return await call_next(request)


# 注册路由
app.include_router(analysis.router)
app.include_router(pages.router)

# 静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "0.1.0"}
