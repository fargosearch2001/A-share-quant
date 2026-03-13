@echo off
chcp 65001 >nul
title 量化回测系统
echo ========================================
echo 启动量化回测系统 Web 界面
echo ========================================
echo.

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [ERROR] 未找到 venv\Scripts\python.exe
  echo [ERROR] 请确认已在项目根目录创建 venv 虚拟环境
  echo.
  pause
  exit /b 1
)

echo [INFO] 正在启动 Streamlit 应用...
echo [INFO] 访问地址: http://localhost:8501
echo.
echo 按 Ctrl+C 停止服务
echo.

start "" "http://localhost:8501"

venv\Scripts\python.exe -m streamlit run src/web/app.py --server.port 8501 --server.headless true
if errorlevel 1 (
  echo.
  echo [ERROR] 启动失败，请查看上方错误信息
  echo.
  pause
  exit /b 1
)

pause
