#!/bin/bash
# 在「阿里云 Ubuntu 服务器」上一键部署/更新「朗读文档」。
#
# 用法（在服务器终端里，先 cd 到本文件所在目录，再用 sudo 运行）：
#     sudo bash deploy_server.sh
#
# 它会：安装组件 → 建虚拟环境装依赖 → 配置开机自启的后台服务 → 启动。
# 重复运行此脚本即可「更新到最新代码」。

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # 仓库根目录
APP_DIR="$REPO_DIR/langdu"                       # 程序目录
PORT=8000

echo "============================================"
echo "  部署「朗读文档」到服务器（端口 $PORT）"
echo "============================================"

echo "[1/5] 安装基础组件（python venv / git）…"
apt-get update -y >/dev/null
apt-get install -y python3-venv python3-pip git >/dev/null

echo "[2/5] 拉取最新代码…"
git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true
git -C "$REPO_DIR" pull --ff-only || echo "（跳过更新，使用当前代码）"

echo "[3/5] 创建虚拟环境并安装依赖…"
cd "$APP_DIR"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
# 服务器版不需要桌面窗口组件 pywebview，只装这几个
.venv/bin/pip install -q flask edge-tts python-docx pypdf

echo "[4/5] 配置后台服务（开机自启）…"
tee /etc/systemd/system/langdu.service >/dev/null <<EOF
[Unit]
Description=Langdu Document Reader
After=network.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python app_lan.py
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable langdu >/dev/null 2>&1 || true
systemctl restart langdu

echo "[5/5] 完成！"
sleep 2
systemctl --no-pager status langdu | head -6 || true

IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "你的服务器IP")
echo ""
echo "============================================"
echo "  ✅ 朗读软件已在后台运行"
echo "  访问地址： http://$IP:$PORT"
echo ""
echo "  ⚠️ 如果手机/电脑打不开，请到阿里云控制台的"
echo "     【安全组】里放行 $PORT 端口（TCP、入方向）。"
echo "============================================"
