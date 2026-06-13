#!/bin/bash
# Mac 双击启动器：打开「朗读文档」应用窗口（独立窗口，不用浏览器）。
# 第一次双击如果被系统拦截，请右键点它选「打开」。

# 切到脚本所在的文件夹（也就是 langdu 目录）
cd "$(dirname "$0")" || exit 1

echo "============================================"
echo "  📖 朗读文档"
echo "============================================"
echo ""

# 检查依赖有没有装好，没装就自动安装
if ! python3 -c "import flask, edge_tts, docx, webview" 2>/dev/null; then
  echo "首次运行，正在安装所需组件（只需要这一次，请稍候）…"
  python3 -m pip install -r requirements.txt
  echo ""
fi

echo "正在打开应用窗口…（窗口出现后，这个黑窗口可以不用管它）"
echo "用完后关掉应用窗口，再回到这里按 Control + C 即可。"
echo ""

# 启动应用窗口（独立窗口，不再打开浏览器）
python3 app_gui.py
