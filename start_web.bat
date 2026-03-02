@echo off
chcp 65001 >nul
title 量化回测系统
echo ========================================
echo 启动量化回测系统 Web 界面
echo ========================================
echo.

cd /d "%~dp0"

echo [INFO] 正在启动 Streamlit 应用...
echo [INFO] 访问地址: http://localhost:8501
echo.
echo 按 Ctrl+C 停止服务
echo.

start "" "http://localhost:8501"

.venv\Scripts\python.exe -m streamlit run src/web/app.py --server.port 8501 --server.headless true

pause
