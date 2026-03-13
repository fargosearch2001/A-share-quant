#!/bin/bash

# 获取脚本所在目录的绝对路径
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=== 正在检查并安装依赖... ==="
# 使用项目内 venv 安装依赖
./venv/Scripts/python.exe -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "依赖安装失败，请检查网络连接或 Python 环境。"
    exit 1
fi

echo "=== 启动回测系统界面... ==="
./venv/Scripts/python.exe -m streamlit run src/web/app.py --server.port 8501
