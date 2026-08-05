@echo off
chcp 65001 >nul
echo ============================================
echo   个人论文分析管理智能体
echo ============================================

REM 先杀掉所有占用 8000 端口的进程
echo [1/2] 清理旧进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo [2/2] 启动服务...
echo.
echo   访问地址: http://localhost:8001
echo   API 文档: http://localhost:8001/docs
echo   按 Ctrl+C 停止
echo.

cd /d %~dp0
uvicorn app.main:app --port 8001 --reload --log-level info
