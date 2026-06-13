#!/bin/bash
# Mac 双击启动器：自动安装依赖、启动朗读软件、打开浏览器。
# 第一次双击如果被系统拦截，请右键点它选「打开」。

# 切到脚本所在的文件夹（也就是 langdu 目录）
cd "$(dirname "$0")" || exit 1

echo "============================================"
echo "  📖 朗读文档小软件"
echo "============================================"
echo ""

# 检查依赖有没有装好，没装就自动安装
if ! python3 -c "import flask, edge_tts, docx" 2>/dev/null; then
  echo "首次运行，正在安装所需组件（只需要这一次，请稍候）…"
  python3 -m pip install -r requirements.txt
  echo ""
fi

# 2 秒后自动用默认浏览器打开界面
( sleep 2 && open "http://127.0.0.1:5000" ) &

echo "软件启动中…浏览器会自动打开 http://127.0.0.1:5000"
echo "用完后，回到这个窗口按 Control + C 即可关闭软件。"
echo ""

# 启动程序
python3 app.py
