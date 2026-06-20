# 本地语音转文字（macOS 版）

一个完全离线的语音转文字小工具，类似 Typeless。
**按一下「右 Option」键开始录音，再按一下结束，文字自动输入到光标处。**

- ✅ 完全离线，语音不联网、不外传（首次需联网下载一次模型）
- ✅ 音频只在内存里处理，识别完即丢弃，不存盘
- ✅ 识别在本地用 faster-whisper 完成

---

## 一、安装步骤（在你的 Mac 上操作）

### 1. 装 Python 和 PortAudio

如果还没装 [Homebrew](https://brew.sh)，先装它，然后：

```bash
brew install python portaudio
```

（`portaudio` 是录音用的底层库，`sounddevice` 依赖它。）

### 2. 装 Python 依赖

建议用虚拟环境，避免污染系统：

```bash
cd yuyin
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 二、授予系统权限（macOS 必需，一次性）

打开「系统设置 → 隐私与安全性」，给运行脚本的程序（**终端 Terminal** 或 **iTerm**）勾选：

1. **麦克风** —— 录音用
2. **辅助功能（Accessibility）** —— 监听全局快捷键、模拟键盘输入用

> 这两项授权只给你本地这个程序，跟联网无关。授权后建议重启一次终端。

---

## 三、运行

```bash
source venv/bin/activate   # 如果刚打开新终端
python3 yuyin.py
```

首次运行会下载模型（默认 small 约 0.5GB），下完之后**可以彻底断网使用**。

看到「本地语音转文字已就绪」后：

1. 把光标放到任意输入框（微信、备忘录、浏览器都行）
2. **按一下右 Option 键**，开始说话
3. **再按一下右 Option 键**结束，稍等 1~2 秒，文字自动输入

按 `Ctrl+C` 退出。

---

## 四、常用调整

打开 `yuyin.py` 顶部「配置区」可改：

| 配置项 | 作用 |
|--------|------|
| `TRIGGER_KEYS` | 触发键集合，默认右 Option，可增删或换别的键 |
| `MODEL_SIZE` | 模型大小，默认 `small`（快而稳）；不够准再换 `medium` / `large-v3` |
| `LANGUAGE` | `"zh"` 中文 / `"en"` 英文 / `None` 自动 |
| `AUTO_PASTE` | `False` 则只复制到剪贴板，不自动粘贴 |
| `DEBUG_SAVE_AUDIO` | 默认 `False`（音频绝不写盘）；排查问题时改 `True`，临时存 wav、识别完自动删 |

### 如果右 Option 触发不灵

不同 Mac、不同键盘对「右 Option」的识别偶尔不稳。若按了没反应，打开 `yuyin.py`
把 `TRIGGER_KEYS` 那行换成下面任一个（实用第一）：

```python
TRIGGER_KEYS = {keyboard.Key.f9}                          # 改用 F9 单键
TRIGGER_KEYS = {keyboard.Key.alt_l, keyboard.Key.alt_r}   # 左右 Option 都行
```

---

## 五、常见问题

**首次运行报 `LocalEntryNotFoundError` / `SSL ... EOF` / 提示检查网络？**
这是下载模型时连不上国外的 Hugging Face（国内常见）。脚本已默认改走国内镜像
`hf-mirror.com`，正常重跑即可。若仍失败，多试一两次，或确认能访问该镜像站。

## 六、安全说明

- 程序内**没有任何网络请求代码**（除首次下载模型；下载只走模型站，不涉及你的语音）。
- 想验证：下载完模型后断开网络，照样能用。
- 录音不写入磁盘；默认也不保存识别历史。

有问题把终端报错贴出来即可，我们再调。
