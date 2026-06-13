#!/bin/bash
# 让手机 / 平板也能用：在电脑上启动，手机连同一个 Wi-Fi 后用浏览器打开提示的网址。
# 第一次双击如果被系统拦截，请右键点它选「打开」。

cd "$(dirname "$0")" || exit 1

echo "============================================"
echo "  📖 朗读文档 · 手机版"
echo "============================================"
echo ""

# 检查依赖有没有装好，没装就自动安装
if ! python3 -c "import flask, edge_tts, docx" 2>/dev/null; then
  echo "首次运行，正在安装所需组件（只需要这一次，请稍候）…"
  python3 -m pip install -r requirements.txt
  echo ""
fi

# 启动局域网服务，并显示手机要打开的网址
python3 app_lan.py
