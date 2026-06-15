# -*- coding: utf-8 -*-
"""
YouTube 文案提取小工具 —— 第一步：有字幕就直接抓字幕
本地网页版：浏览器打开网址，粘贴链接，点按钮，出 txt 文字稿。
"""

import os
import re
import glob
import tempfile
import datetime

from flask import Flask, request, render_template, send_file, jsonify

app = Flask(__name__)

# 文字稿保存到这个文件夹（和本文件同目录下的 outputs）
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 字幕语言优先顺序：简体中文 -> 繁体中文 -> 中文 -> 英文（各种变体都照顾到）
LANG_PRIORITY = [
    "zh-Hans", "zh-CN", "zh-Hans-CN", "zh",
    "zh-Hant", "zh-TW", "zh-HK",
    "en", "en-US", "en-GB", "en-orig",
]


def clean_filename(name: str) -> str:
    """把视频标题里不能做文件名的字符去掉。"""
    name = re.sub(r"[\\/:*?\"<>|\n\r\t]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:80] if name else "youtube_transcript"


def vtt_to_text(vtt_path: str) -> str:
    """把 .vtt 字幕文件转成干净的纯文字（去时间轴、去标签、去重复行）。"""
    with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # 跳过 WEBVTT 头、序号、时间轴、样式说明
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if line.startswith("NOTE") or line.startswith("STYLE"):
            continue
        # 去掉 <00:00:00.000> 这类时间标签和 <c> 这类样式标签
        line = re.sub(r"<[^>]+>", "", line)
        line = line.strip()
        if not line:
            continue
        lines.append(line)

    # 自动字幕常有相邻重复行，去掉连续重复
    deduped = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)

    return "\n".join(deduped).strip()


def fetch_subtitle(url: str):
    """
    用 yt-dlp 抓字幕。
    返回 (成功?, 文字稿内容或错误信息, 视频标题, 用的是哪种语言)
    """
    try:
        import yt_dlp
    except ImportError:
        return False, "缺少 yt-dlp 库，请先安装（见使用说明）。", None, None

    with tempfile.TemporaryDirectory() as tmp:
        outtmpl = os.path.join(tmp, "%(id)s.%(ext)s")
        ydl_opts = {
            "skip_download": True,          # 不下载视频本身
            "writesubtitles": True,         # 抓人工字幕
            "writeautomaticsub": True,      # 抓 YouTube 自动生成的字幕
            "subtitleslangs": LANG_PRIORITY,
            "subtitlesformat": "vtt",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
        }

        title = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title")
        except Exception as e:
            return False, f"抓取失败：{e}", None, None

        # 在临时目录里找下载到的 .vtt 字幕，按语言优先级挑一个
        vtt_files = glob.glob(os.path.join(tmp, "*.vtt"))
        if not vtt_files:
            return False, "NO_SUBTITLE", title, None

        chosen = None
        chosen_lang = None
        for lang in LANG_PRIORITY:
            for vf in vtt_files:
                # 文件名形如  videoid.zh-Hans.vtt
                if re.search(r"\." + re.escape(lang) + r"\.vtt$", vf):
                    chosen = vf
                    chosen_lang = lang
                    break
            if chosen:
                break
        if not chosen:
            chosen = vtt_files[0]
            m = re.search(r"\.([^.]+)\.vtt$", os.path.basename(chosen))
            chosen_lang = m.group(1) if m else "未知"

        text = vtt_to_text(chosen)
        if not text:
            return False, "字幕文件是空的，可能这个视频没有可用文字。", title, chosen_lang

        return True, text, title, chosen_lang


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "msg": "请先粘贴一个 YouTube 视频链接。"})

    ok, result, title, lang = fetch_subtitle(url)

    if not ok and result == "NO_SUBTITLE":
        return jsonify({
            "ok": False,
            "no_subtitle": True,
            "msg": "这个视频没有找到字幕（人工和自动字幕都没有）。\n"
                   "这正是第二步要解决的情况：下载音频用语音识别转文字。\n"
                   "我们会在第二步加上这个兜底功能。",
        })

    if not ok:
        return jsonify({"ok": False, "msg": result})

    # 保存成 txt 文件
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{clean_filename(title or 'transcript')}_{stamp}.txt"
    fpath = os.path.join(OUTPUT_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(result)

    return jsonify({
        "ok": True,
        "title": title,
        "lang": lang,
        "filename": fname,
        "chars": len(result),
        "preview": result[:1500],
    })


@app.route("/download/<path:filename>")
def download(filename):
    fpath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(fpath):
        return "文件不存在", 404
    return send_file(fpath, as_attachment=True)


if __name__ == "__main__":
    print("=" * 50)
    print("文案提取小工具已启动！")
    print("请在浏览器打开： http://127.0.0.1:5000")
    print("关闭工具：回到这个窗口按 Control + C")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5000, debug=False)
