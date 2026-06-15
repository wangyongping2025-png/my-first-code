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

import organizer

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


def _looks_like_bot_block(err: str) -> bool:
    """判断错误是不是 YouTube 的『证明你不是机器人』拦截。"""
    e = (err or "").lower()
    return ("sign in to confirm" in e) or ("not a bot" in e) or ("cookies" in e)


def _do_extract(url: str, tmp: str, cookies_browser):
    """跑一次 yt-dlp 抓字幕。cookies_browser 可为 None 或 'chrome'/'safari' 等。"""
    import yt_dlp
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
    if cookies_browser:
        # 借用浏览器里的 YouTube 登录身份，绕过『证明你不是机器人』
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=True)


def fetch_subtitle(url: str):
    """
    用 yt-dlp 抓字幕。
    返回 (成功?, 文字稿内容或错误信息, 视频标题, 用的是哪种语言)
    """
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return False, "缺少 yt-dlp 库，请先安装（见使用说明）。", None, None

    with tempfile.TemporaryDirectory() as tmp:
        title = None
        last_err = None
        info = None
        # 依次尝试：① 不带登录身份 ② 借 Chrome 的登录身份 ③ 借 Safari 的登录身份
        for browser in (None, "chrome", "safari"):
            # 清掉上一次尝试可能留下的字幕文件
            for f in glob.glob(os.path.join(tmp, "*.vtt")):
                try:
                    os.remove(f)
                except OSError:
                    pass
            try:
                info = _do_extract(url, tmp, browser)
                title = info.get("title")
                last_err = None
                break
            except Exception as e:
                last_err = str(e)
                # 只有遇到『机器人拦截』才值得换浏览器登录身份再试；其它错误直接停
                if _looks_like_bot_block(last_err):
                    continue
                break

        if info is None:
            if last_err and _looks_like_bot_block(last_err):
                return False, "YOUTUBE_BOT", None, None
            return False, f"抓取失败：{last_err}", None, None

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

    if not ok and result == "YOUTUBE_BOT":
        return jsonify({
            "ok": False,
            "msg": "YouTube 要求『证明你不是机器人』，自动用浏览器身份也没通过。\n"
                   "请这样做：\n"
                   "1）用 Chrome 或 Safari 打开 youtube.com 并登录你的账号；\n"
                   "2）保持登录状态，回到本页面再点一次「提取文案」。\n"
                   "（工具会借用你浏览器里的 YouTube 登录身份来通过验证，只在你本地进行。）",
        })

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

    raw_text = result  # 原始未整理文案

    # 调用 Claude 智能整理
    ok2, md, changelog = organizer.organize(raw_text, title, url, lang)

    if not ok2 and md == "NO_API_KEY":
        return jsonify({
            "ok": False,
            "msg": "字幕已经抓到了，但还没法整理：没有找到 DeepSeek 的 API key。\n"
                   "请把你的 key 粘贴到 wenan 文件夹里的 apikey.txt 文件中（见使用说明），再点一次。",
        })
    if not ok2:
        return jsonify({"ok": False, "msg": "字幕抓到了，但整理这一步出错：\n" + md})

    # 保存三个文件：原始 txt、整理 md、处理记录 md
    base = clean_filename(title or "transcript")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_name = f"{base}_原始_{stamp}.txt"
    md_name = f"{base}_整理_{stamp}.md"
    log_name = f"{base}_处理记录_{stamp}.md"

    with open(os.path.join(OUTPUT_DIR, raw_name), "w", encoding="utf-8") as f:
        f.write(raw_text)
    with open(os.path.join(OUTPUT_DIR, md_name), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(OUTPUT_DIR, log_name), "w", encoding="utf-8") as f:
        f.write(changelog)

    raw_chars = len(raw_text)
    md_chars = len(md)
    ratio = round(md_chars / raw_chars * 100) if raw_chars else 0

    return jsonify({
        "ok": True,
        "title": title,
        "lang": lang,
        "raw_chars": raw_chars,
        "md_chars": md_chars,
        "ratio": ratio,
        "raw_name": raw_name,
        "md_name": md_name,
        "log_name": log_name,
        "preview": md[:1800],
        "save_dir": OUTPUT_DIR,
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
    print("请在浏览器打开： http://127.0.0.1:5050")
    print("关闭工具：回到这个窗口按 Control + C")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5050, debug=False)
