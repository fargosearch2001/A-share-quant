# PowerShell 启动脚本
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "启动量化回测系统 Web 界面" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot

Write-Host "正在启动 Streamlit 应用..." -ForegroundColor Yellow
Write-Host "访问地址: http://localhost:8501" -ForegroundColor Green
Write-Host ""
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

# 启动 Streamlit，指定固定端口 8501
.venv\Scripts\python.exe -m streamlit run src/web/app.py --server.port 8501 --server.headless true
