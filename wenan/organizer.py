# -*- coding: utf-8 -*-
"""
整理模块：把抓到的原始文案，按用户那套规则用 DeepSeek 智能整理。
产出：整理好的 Markdown 正文 + 一份「删除与调整记录」。
DeepSeek 在国内可直接使用，支付宝/微信充值，中文整理质量好。
"""

import os

# DeepSeek 的接口地址和模型（deepseek-chat = DeepSeek-V3，速度快、便宜、中文好）
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

# 整理规则（完全对应你文档里的「二、整理规则」）写成给 AI 的系统指令
SYSTEM_PROMPT = """你是一个中文视频文案整理专家。用户会给你一段视频的原始文字稿（可能来自人工字幕或自动字幕），\
请严格按下面的规则整理，并输出两部分内容。

【轻度语言整理】
1. 删除「啊、嗯、呃、好吧」等不承载信息的语气词。
2. 删除口吃式或机械式重复，例如「下滑、下滑」「改革开放，改革开放」。
3. 合并完全相同、没有新增信息的重复语句。
4. 删除「傻逼」这类不承载信息的侮辱性粗口，但必须保留该句的实际观点。
5. 补全并纠正标点符号。
6. 修复自动字幕造成的断句错误、错别字、同音字和明显识别错误。
7. 调整不通顺的语序，使表达自然、逻辑连贯。

【内容保留原则（最重要，不许偷工）】
1. 只清理语言，不缩写内容；只优化表达，不删减信息。
2. 必须保留人名、时间、数字、历史案例、观点、预测、论据和结论。
3. 意思相近但包含新增信息的句子，必须保留。
4. 不得因为观点重复、表达尖锐或有争议就删除有效内容。
5. 与主线关系较弱但有信息的直播问答，移到文末「直播互动与延伸讨论」，不得直接删除。
6. 不要擅自总结、压缩或改变讲话者的原意和立场。
7. 无法确认的字幕内容不要自行编造，可保留并注明「（此处可能存在识别错误）」。
8. 整理后正文原则上保留原文 85%–95% 的信息量；减少超过 15% 时，必须在处理记录里说明原因。

【翻译】
如果原文不是中文，请准确翻译成简体中文后再按上述规则整理；保持原意，不要漏译。

【Markdown 排版】
1. 根据内容主题划分章节，加准确、简洁的小标题。
2. 按语义合理分段，避免大段文字堆积。
3. 文档开头注明视频来源和字幕整理说明。
4. 重要原话可用 Markdown 引用格式（> ）。
5. 偏离主线但有信息的内容，统一放入「直播互动与延伸讨论」。

【处理记录】
另外生成一份简短的「删除与调整记录」：
1. 列出有代表性的：原文、整理结果、处理原因。
2. 如果删除了包含实际信息的完整句子，必须逐条列出并说明理由。
3. 如果只删了语气词、重复、无信息粗口，列举几个代表性示例即可。

【输出格式（务必严格遵守）】
先输出整理好的 Markdown 正文，然后另起一行输出一行分隔标记，再输出处理记录，像这样：

===MARKDOWN===
（这里是整理好的 Markdown 正文）
===CHANGELOG===
（这里是删除与调整记录）

不要输出除这两部分以外的任何多余说明。"""


def get_api_key():
    """先找本地 apikey.txt，再找环境变量。返回 key 或 None。"""
    here = os.path.dirname(os.path.abspath(__file__))
    f = os.path.join(here, "apikey.txt")
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fp:
            key = fp.read().strip()
            if key:
                return key
    return os.environ.get("DEEPSEEK_API_KEY")


def organize(raw_text: str, title: str, url: str, lang: str):
    """
    调用 DeepSeek 整理。返回 (成功?, markdown或错误信息, changelog)
    """
    key = get_api_key()
    if not key:
        return False, "NO_API_KEY", None

    try:
        from openai import OpenAI
        import openai as openai_pkg
    except ImportError:
        return False, "缺少 openai 库，请先安装（见使用说明）。", None

    client = OpenAI(api_key=key, base_url=BASE_URL, timeout=600)

    user_msg = (
        f"视频标题：{title or '(未知)'}\n"
        f"视频链接：{url}\n"
        f"字幕语言：{lang}\n\n"
        f"下面是原始文字稿，请按规则整理：\n\n{raw_text}"
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            max_tokens=8192,           # DeepSeek 单次最多输出 8192
            temperature=0.3,           # 稍低，整理任务更稳
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
    except openai_pkg.AuthenticationError:
        return False, "API key 无效或填错了，请检查 apikey.txt 里粘贴的密钥。", None
    except openai_pkg.PermissionDeniedError:
        return False, "这个 API key 没有权限，或账户还没充值。请到 platform.deepseek.com 充值。", None
    except openai_pkg.RateLimitError:
        return False, "请求太频繁或余额不足，被限流了。等几十秒再试，或检查账户余额。", None
    except openai_pkg.APIConnectionError:
        return False, "连不上 DeepSeek 服务器，请检查网络后重试。", None
    except Exception as e:
        return False, f"整理失败：{e}", None

    text = (resp.choices[0].message.content or "").strip()

    # 按分隔标记切成 markdown 和 changelog 两部分
    if "===CHANGELOG===" in text:
        md_part, log_part = text.split("===CHANGELOG===", 1)
    else:
        md_part, log_part = text, "（本次未生成处理记录）"
    md_part = md_part.replace("===MARKDOWN===", "").strip()
    log_part = log_part.strip()

    if not md_part:
        return False, "整理结果是空的，请重试一次。", None

    return True, md_part, log_part
