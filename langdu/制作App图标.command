#!/bin/bash
# 只需运行一次：在「桌面」上生成一个真正的「朗读文档.app」图标。
# 生成后双击桌面图标即可打开，不再需要终端；关掉窗口就退出。
#
# 原理：在本机现做一个 .app 应用包，并把程序文件复制进去（自带运行），
# 这样 App 可以独立存在，也能拖到 Dock 栏。

set -e
cd "$(dirname "$0")" || exit 1
SRC="$(pwd)"
APP="$HOME/Desktop/朗读文档.app"

# 找到当前可用的 python3 的真实路径，写死进 App，
# 这样从图标启动时（环境变量较少）也一定能找到 Python。
PYBIN="$(command -v python3)"
if [ -z "$PYBIN" ]; then
  echo "❌ 没找到 python3，请先确认 Python 已安装。"
  exit 1
fi

echo "正在制作「朗读文档.app」…"

# 先清掉旧的，再重建目录结构
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources/code"

# 把程序文件复制进 App 里，让它能独立运行
cp "$SRC/app.py" "$SRC/app_gui.py" "$SRC/requirements.txt" "$APP/Contents/Resources/code/"
cp -R "$SRC/templates" "$APP/Contents/Resources/code/"

# 写 App 的描述文件 Info.plist
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>朗读文档</string>
  <key>CFBundleDisplayName</key><string>朗读文档</string>
  <key>CFBundleIdentifier</key><string>com.laowang.langdu</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>run</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# 写 App 内部真正的启动脚本（双击图标时会执行它，不弹终端）
cat > "$APP/Contents/MacOS/run" <<RUN
#!/bin/bash
DIR="\$(cd "\$(dirname "\$0")/../Resources/code" && pwd)"
cd "\$DIR"
PY="$PYBIN"
# 万一缺组件就装一下（一般你已经装过，会直接跳过）
if ! "\$PY" -c "import flask, edge_tts, docx, webview" 2>/dev/null; then
  "\$PY" -m pip install -r requirements.txt
fi
exec "\$PY" app_gui.py
RUN
chmod +x "$APP/Contents/MacOS/run"

echo ""
echo "✅ 完成！你的「桌面」上出现了一个「朗读文档」图标。"
echo "   以后双击桌面那个图标即可打开，不再需要终端。"
echo "   也可以把它拖到 Dock 栏常驻。"
echo ""

# 在访达里高亮显示刚生成的 App
open -R "$APP"
