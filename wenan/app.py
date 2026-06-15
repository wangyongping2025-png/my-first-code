# -*- coding: utf-8 -*-
"""
YouTube 文案提取小工具 —— 第一步：有字幕就直接抓字幕
本地网页版：浏览器打开网址，粘贴链接，点按钮，出 txt 文字稿。
"""

import os
import re
import glob
import time
import tempfile
import datetime

from flask import Flask, request, render_template, send_file, jsonify

app = Flask(__name__)

# 给你粘到 Claude / ChatGPT 用的整理指令（内容不经过任何云，整理在你自己的会员里做）
ORGANIZE_INSTRUCTION = """请你帮我整理下面这段视频文字稿，按以下规则处理，并输出两部分内容。

【轻度语言整理】
1. 删除"啊、嗯、呃、好吧"等不承载信息的语气词。
2. 删除口吃式或机械式重复（如"下滑、下滑""改革开放，改革开放"）。
3. 合并完全相同、没有新增信息的重复语句。
4. 删除"傻逼"这类不承载信息的侮辱性粗口，但必须保留该句的实际观点。
5. 补全并纠正标点符号。
6. 修复自动字幕造成的断句错误、错别字、同音字和明显识别错误。
7. 调整不通顺的语序，使表达自然、逻辑连贯。

【内容保留原则（最重要，不许偷工）】
1. 只清理语言，不缩写内容；只优化表达，不删减信息。
2. 必须保留人名、时间、数字、历史案例、观点、预测、论据和结论。
3. 意思相近但包含新增信息的句子，必须保留。
4. 不得因为观点重复、表达尖锐或有争议就删除有效内容。
5. 与主线关系较弱但有信息的内容，移到文末"延伸讨论"，不得直接删除。
6. 不要擅自总结、压缩或改变讲话者的原意和立场。
7. 无法确认的内容不要编造，可保留并注明"（此处可能存在识别错误）"。
8. 整理后正文原则上保留原文 85%–95% 的信息量；减少超过 15% 时请说明原因。

【如果原文不是中文】请准确翻译成简体中文后再按上述规则整理。

【Markdown 排版】
1. 按主题划分章节、加准确简洁的小标题。
2. 合理分段，避免大段堆积。
3. 开头注明视频来源和整理说明。
4. 重要原话可用引用格式（> ）。

【处理记录】最后附一份简短的"删除与调整记录"，举几个代表性例子（原文 → 整理结果 → 原因）。

下面是文字稿："""

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


# 翻墙软件的本地代理（鸟云加速：127.0.0.1:6376）。端口变了就在 wenan 里建 proxy.txt 改。
DEFAULT_PROXY = "http://127.0.0.1:6376"


def get_proxy():
    """优先读 proxy.txt，否则用默认代理。返回形如 http://127.0.0.1:6376，写 none 表示不走代理。"""
    here = os.path.dirname(os.path.abspath(__file__))
    f = os.path.join(here, "proxy.txt")
    val = ""
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fp:
            val = fp.read().strip()
    if not val:
        val = DEFAULT_PROXY
    if val.lower() in ("none", "no", "off", "关闭", "不走代理"):
        return None
    if "://" not in val:
        val = "http://" + val
    return val


def _looks_like_bot_block(err: str) -> bool:
    """判断错误是不是 YouTube 的『证明你不是机器人』拦截。"""
    e = (err or "").lower()
    return ("sign in to confirm" in e) or ("not a bot" in e) or ("--cookies" in e)


def _looks_like_network(err: str) -> bool:
    """判断错误是不是线路/网络抖动（值得重试）。"""
    e = (err or "").lower()
    keys = ("ssl", "eof", "timed out", "timeout", "connection", "unable to download",
            "getaddrinfo", "reset by peer", "read operation", "proxy", "tunnel", "10054", "broken pipe")
    return any(k in e for k in keys)


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
        # 我们只要字幕，不下载视频画面；挑不到视频格式也不影响抓字幕
        "ignore_no_formats_error": True,
        "socket_timeout": 30,
    }
    proxy = get_proxy()
    if proxy:
        # 固定走你的翻墙软件本地代理，避免系统路由不稳导致 SSL 断开
        ydl_opts["proxy"] = proxy
    if cookies_browser:
        # 借用浏览器里的 YouTube 登录身份，绕过『证明你不是机器人』
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=True)


def _pick_subtitle_text(tmp: str):
    """从临时目录里按语言优先级挑一个字幕，返回 (文字, 语言)，没有就 (None, None)。"""
    vtt_files = glob.glob(os.path.join(tmp, "*.vtt"))
    if not vtt_files:
        return None, None
    chosen = None
    chosen_lang = None
    for lang in LANG_PRIORITY:
        for vf in vtt_files:
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
    return vtt_to_text(chosen), chosen_lang


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
        saw_bot = False
        saw_network = False
        got_info = False

        # 依次用 ① 不带登录身份 ② Chrome 登录身份 ③ Safari 登录身份；哪个先拿到字幕就用哪个
        for browser in (None, "chrome", "safari"):
            info = None
            err = None
            # 线路抖动就重试，每个身份最多试 3 次
            for _ in range(3):
                for f in glob.glob(os.path.join(tmp, "*.vtt")):
                    try:
                        os.remove(f)
                    except OSError:
                        pass
                try:
                    info = _do_extract(url, tmp, browser)
                    err = None
                    break
                except Exception as e:
                    err = str(e)
                    if _looks_like_network(err) and not _looks_like_bot_block(err):
                        saw_network = True
                        time.sleep(2)
                        continue  # 线路抖动，重试同一身份
                    break  # 机器人拦截或其它错误，换下一个身份

            if info is None:
                if err and _looks_like_bot_block(err):
                    saw_bot = True
                continue  # 换下一个登录身份

            got_info = True
            title = info.get("title") or title
            text, lang = _pick_subtitle_text(tmp)
            if text:
                return True, text, title, lang
            # 这个身份没拿到字幕，换下一个身份再试

        # 三种身份都试完，仍没字幕
        if not got_info and saw_network:
            return False, "NETWORK_ERROR", title, None
        if not got_info and saw_bot:
            return False, "YOUTUBE_BOT", title, None
        return False, "NO_SUBTITLE", title, None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "msg": "请先粘贴一个 YouTube 视频链接。"})

    ok, result, title, lang = fetch_subtitle(url)

    if not ok and result == "NETWORK_ERROR":
        return jsonify({
            "ok": False,
            "msg": "连 YouTube 的网络不稳定，自动重试多次还是断了。\n"
                   "请确认翻墙软件已连接、换个更稳的节点，再点一次「提取文案」。\n"
                   "（工具已自动走你的代理 127.0.0.1:6376；如果你的代理端口变了，把新端口写进 wenan 文件夹里的 proxy.txt。）",
        })

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

    raw_text = result  # 抓到的原始文字稿

    # 不上传任何云：只把原始文字稿存成 txt，并拼好一份"整理指令+文字稿"供你粘到 Claude / GPT
    base = clean_filename(title or "transcript")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_name = f"{base}_文字稿_{stamp}.txt"
    with open(os.path.join(OUTPUT_DIR, raw_name), "w", encoding="utf-8") as f:
        f.write(raw_text)

    paste_package = (
        ORGANIZE_INSTRUCTION
        + f"\n\n视频标题：{title or '(未知)'}\n视频链接：{url}\n\n"
        + raw_text
    )

    return jsonify({
        "ok": True,
        "title": title,
        "lang": lang,
        "chars": len(raw_text),
        "raw_name": raw_name,
        "raw_text": raw_text,
        "paste": paste_package,
        "preview": raw_text[:1500],
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
