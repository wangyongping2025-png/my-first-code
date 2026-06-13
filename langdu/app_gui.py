# -*- coding: utf-8 -*-
"""把朗读软件显示在一个独立的应用窗口里（而不是浏览器）。

用 pywebview 打开一个原生窗口，窗口里运行的就是和网页版完全一样的界面，
但不再需要打开浏览器，看起来、用起来都更像一个真正的 App。

运行方法（macOS）：
    python3 app_gui.py
（更简单：双击「启动朗读软件.command」）
"""

import threading
import time
import urllib.request

import webview

from app import app  # 复用网页版里写好的全部功能

PORT = 8000
URL = f"http://127.0.0.1:{PORT}"


def run_server():
    """在后台线程里启动 Flask 服务（窗口关掉后随程序一起结束）。"""
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


def wait_until_ready(timeout=15):
    """等后台服务真正起来了，窗口再加载，避免出现空白页。"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    threading.Thread(target=run_server, daemon=True).start()
    wait_until_ready()
    # 打开一个原生应用窗口
    webview.create_window("朗读文档", URL, width=840, height=960)
    webview.start()


if __name__ == "__main__":
    main()
