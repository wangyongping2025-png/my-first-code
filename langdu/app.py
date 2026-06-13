# -*- coding: utf-8 -*-
"""朗读文档小软件

上传 Word（.docx）、TXT 或 Markdown（.md）文档，
选择喜欢的普通话声音，用自然流畅、富有感情的声音朗读出来。
支持长文档自动分段、逐段朗读、暂停/继续、从任意一段开始。

语音引擎：微软 Edge 神经网络语音（edge-tts），免费、音质自然、有情感起伏。

运行方法（macOS）：
    pip3 install -r requirements.txt
    python3 app.py
然后用浏览器打开 http://127.0.0.1:8000
（更简单的办法：直接双击「启动朗读软件.command」）

说明：端口用 8000，避开 macOS「隔空播放接收器」默认占用的 5000 端口。
"""

import asyncio
import io
import re

import edge_tts
from docx import Document
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 最大 20MB

# 可选的普通话声音（都是自然有感情的神经网络语音）
VOICES = {
    "zh-CN-XiaoxiaoNeural": {"name": "晓晓", "gender": "女声", "desc": "温暖亲切 · 通用", "emoji": "👩"},
    "zh-CN-XiaoyiNeural":   {"name": "晓伊", "gender": "女声", "desc": "活泼灵动 · 适合故事", "emoji": "👧"},
    "zh-CN-YunxiNeural":    {"name": "云希", "gender": "男声", "desc": "自然清爽 · 通用", "emoji": "👨"},
    "zh-CN-YunjianNeural":  {"name": "云健", "gender": "男声", "desc": "浑厚稳重 · 大气", "emoji": "🧔"},
    "zh-CN-YunyangNeural":  {"name": "云扬", "gender": "男声", "desc": "专业播报 · 新闻感", "emoji": "📻"},
    "zh-CN-YunxiaNeural":   {"name": "云夏", "gender": "男声", "desc": "少年清亮 · 讲故事", "emoji": "🧒"},
}
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


# ---------- 文档解析 ----------

def read_txt(data: bytes) -> str:
    """读取 TXT，自动尝试常见中文编码。"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError("无法识别文件编码，请用 UTF-8 或 GBK 编码保存后重试")


def read_docx(data: bytes) -> str:
    """读取 Word 文档，按段落提取文字。"""
    doc = Document(io.BytesIO(data))
    paragraphs = [p.text.strip() for p in doc.paragraphs]
    return "\n".join(p for p in paragraphs if p)


def read_md(data: bytes) -> str:
    """读取 Markdown，去掉标记符号，只留下正文文字。"""
    text = read_txt(data)
    text = re.sub(r"```.*?```", "", text, flags=re.S)        # 代码块
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # 图片
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)      # 链接保留文字
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)        # 标题井号
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)      # 列表符号
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)      # 有序列表
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)          # 引用符号
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.M) # 分隔线
    text = re.sub(r"(\*\*|__|\*|_|`|~~)", "", text)           # 加粗斜体等
    text = re.sub(r"\|", " ", text)                           # 表格竖线
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".docx"):
        return read_docx(data)
    if name.endswith((".md", ".markdown")):
        return read_md(data)
    if name.endswith(".txt"):
        return read_txt(data).strip()
    if name.endswith(".doc"):
        raise ValueError("暂不支持老版 .doc 格式，请用 Word 另存为 .docx 后再上传")
    raise ValueError("只支持 .docx、.txt、.md 格式的文档")


# ---------- 语音合成 ----------

async def synthesize(text: str, voice: str, rate: str) -> bytes:
    """调用 edge-tts 把文字合成为 MP3 音频。"""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    audio = buffer.getvalue()
    if not audio:
        raise RuntimeError("没有生成任何音频")
    return audio


# ---------- 网页接口 ----------

@app.route("/")
def index():
    return render_template("index.html", voices=VOICES, default_voice=DEFAULT_VOICE)


@app.route("/sw.js")
def service_worker():
    """从根路径提供 Service Worker，让它的作用范围覆盖整个站点。"""
    resp = app.send_static_file("sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/extract", methods=["POST"])
def api_extract():
    """上传文档，返回提取出来的文字。"""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "请先选择一个文档"}), 400
    try:
        text = extract_text(file.filename, file.read())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "文档解析失败，请确认文件没有损坏"}), 400
    if not text:
        return jsonify({"error": "这个文档里没有找到文字内容"}), 400
    return jsonify({"text": text, "chars": len(text)})


@app.route("/api/tts", methods=["POST"])
def api_tts():
    """把一段文字合成为语音，返回 MP3。"""
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "没有可朗读的文字"}), 400

    voice = payload.get("voice")
    if voice not in VOICES:
        voice = DEFAULT_VOICE

    # 语速：-50 ~ +50（百分比），默认原速
    try:
        speed = max(-50, min(50, int(payload.get("speed", 0))))
    except (TypeError, ValueError):
        speed = 0
    rate = f"{speed:+d}%"

    try:
        audio = asyncio.run(synthesize(text, voice, rate))
    except Exception as e:
        message = str(e)
        if "403" in message:
            message = "语音服务拒绝了请求（403）。请检查网络后重试。"
        else:
            message = "语音合成失败：" + message
        return jsonify({"error": message}), 502

    return send_file(io.BytesIO(audio), mimetype="audio/mpeg",
                     as_attachment=False, download_name="朗读.mp3")


if __name__ == "__main__":
    print("朗读文档小软件已启动，请用浏览器打开 http://127.0.0.1:8000")
    print("（按 Control + C 可以停止软件）")
    app.run(host="127.0.0.1", port=8000, debug=False)
