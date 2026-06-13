# -*- coding: utf-8 -*-
"""手机 / 平板也能用：让同一个 Wi-Fi 下的手机通过浏览器访问朗读软件。

电脑运行这个文件后，屏幕上会显示一个网址；在手机浏览器里打开那个网址，
就能用手机操作朗读软件了。

要求：
- 手机和这台电脑连「同一个 Wi-Fi」
- 这台电脑要一直开着、运行着（别关启动窗口）
"""

import socket

from app import app  # 复用网页版的全部功能

PORT = 8000


def get_lan_ip() -> str:
    """获取本机在局域网（Wi-Fi）里的 IP 地址。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不会真的发数据，只是借此拿到本机的出口 IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    ip = get_lan_ip()
    line = "=" * 46
    print(line)
    print("  📱 手机 / 平板 访问方式")
    print(line)
    print()
    print(f"  在手机浏览器里打开这个网址：")
    print(f"      http://{ip}:{PORT}")
    print()
    print("  注意：")
    print("  · 手机要和这台电脑连「同一个 Wi-Fi」")
    print("  · 这台电脑要一直开着，别关这个窗口")
    print("  · 第一次系统若弹窗问“是否允许接入网络连接”，请点“允许”")
    print("  · 用完后按 Control + C 关闭")
    print()
    print(line)
    # host=0.0.0.0 表示允许同一 Wi-Fi 下的其它设备（手机）访问
    app.run(host="0.0.0.0", port=PORT, debug=False)
