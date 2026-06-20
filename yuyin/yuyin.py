#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地语音转文字工具（macOS 版，第一版）

用法：
    按一下 右 Option 键开始录音，再按一下结束并识别，
    识别出的文字会自动「粘贴」到你当前光标所在的位置。

特点：
    - 完全离线：识别在本地完成，语音不联网、不外传。
    - 音频不落盘：录音只存在内存里，识别完即丢弃。

依赖见 requirements.txt，首次运行会下载一次模型文件（之后可彻底断网使用）。
"""

import os
import sys
import time
import wave
import tempfile
import threading
import subprocess

# 模型托管在 Hugging Face，国内直连常不稳定/连不上。
# 默认改走国内镜像 hf-mirror.com，避免「首次下载模型」卡住。
# 如果你能直连或人在国外，可删掉下面这行，或用环境变量 HF_ENDPOINT 覆盖。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import numpy as np
import sounddevice as sd
import pyperclip
from pynput import keyboard
from faster_whisper import WhisperModel


# ============ 配置区（这里可以按需修改） ============

# 触发键：按一下开始录音，再按一下结束并识别（开关模式）。
# 默认只用「右 Option」，这个键平时基本不用，不会和输入法切换、特殊符号冲突。
#
# 【备用方案】万一你的 Mac 上右 Option 触发不灵，换成下面任意一行即可（实用第一）：
#   TRIGGER_KEYS = {keyboard.Key.f9}                       # 用 F9 单键
#   TRIGGER_KEYS = {keyboard.Key.alt_l, keyboard.Key.alt_r}  # 左右 Option 都行
TRIGGER_KEYS = {keyboard.Key.alt_r}

# 识别语言："zh" 中文；"en" 英文；None 自动检测。
LANGUAGE = "zh"

# 模型大小：tiny / base / small / medium / large-v3
# 第一版用 small：在 8G 内存的 Mac 上又快又稳，中文够用。
# 觉得不够准，再依次往上换 medium / large-v3（更准但更慢、更占内存）。
MODEL_SIZE = "small"

# 计算精度。Apple Silicon / CPU 用 "int8" 兼容性最好、占用最低。
COMPUTE_TYPE = "int8"

# 采样率，Whisper 用 16000。
SAMPLE_RATE = 16000

# 识别完是否自动粘贴到光标处。False 则只放进剪贴板，你自己按 Cmd+V。
AUTO_PASTE = True

# 调试开关：默认 False，音频只在内存处理、绝不写盘（最安全）。
# 排查「录音/识别有没有问题」时临时改成 True：会把每段录音存成 wav，
# 识别完成后自动删除；存放在临时目录，路径会打印在终端，方便你回放检查。
DEBUG_SAVE_AUDIO = False

# 调试开关：改成 True 后，按任意键都会在终端打印出来。
# 用来排查「按键没反应」——能看到打印就说明监听正常，也能看清各键的真实名字。
SHOW_KEYS = False

# 声音提示：开始录音「叮」、结束录音「啵」、出字「叮咚」。
# 这样不用盯着终端，在任何软件里靠声音就知道状态。
SOUND_FEEDBACK = True

# 屏幕浮动提示：录音/识别时在屏幕底部中间显示一个悬浮小条（像 Typeless）。
# 这样不用看终端就知道当前状态。
SHOW_OVERLAY = True

# ====================================================


class VoiceTyper:
    def __init__(self):
        print(f"正在加载模型 {MODEL_SIZE}（首次会下载，请稍候）...")
        self.model = WhisperModel(MODEL_SIZE, device="cpu", compute_type=COMPUTE_TYPE)
        print("模型加载完成。")

        self._recording = False
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()
        self._kb = keyboard.Controller()
        # 标记触发键当前是否处于按下状态，用来过滤长按时系统连发的重复事件
        self._key_down = False
        # 当前状态："idle" 空闲 / "recording" 录音中 / "transcribing" 识别中
        # 浮动提示窗口靠读这个值来决定显示什么
        self.status = "idle"

    # ---------- 录音 ----------

    def _beep(self, sound):
        # 用 macOS 自带系统声音做提示，非阻塞播放
        if not SOUND_FEEDBACK:
            return
        path = f"/System/Library/Sounds/{sound}.aiff"
        try:
            subprocess.Popen(
                ["afplay", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            # 录音底层有警告时打印出来，但不中断
            print(f"[录音警告] {status}", file=sys.stderr)
        self._frames.append(indata.copy())

    def start_recording(self):
        with self._lock:
            if self._recording:
                return
            self._recording = True
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            self.status = "recording"
            self._beep("Tink")  # 「叮」：开始录音
            print("🎙️  正在录音...（再按一下结束）")

    def stop_recording_and_transcribe(self):
        with self._lock:
            if not self._recording:
                return
            self._recording = False
            self._stream.stop()
            self._stream.close()
            self._stream = None
            frames = self._frames
            self._frames = []

        self._beep("Pop")  # 「啵」：结束录音、开始识别
        self.status = "transcribing"
        try:
            if not frames:
                print("没有录到声音。")
                return

            audio = np.concatenate(frames, axis=0).flatten().astype(np.float32)
            duration = len(audio) / SAMPLE_RATE
            if duration < 0.3:
                print("录音太短，已忽略。")
                return

            print(f"🧠  识别中...（{duration:.1f} 秒音频）")

            # 调试模式：临时存个 wav 方便检查，识别完在 finally 里删掉
            debug_path = self._save_debug_wav(audio) if DEBUG_SAVE_AUDIO else None
            try:
                self._transcribe(audio)
            finally:
                if debug_path and os.path.exists(debug_path):
                    os.remove(debug_path)
                    print(f"🧹  已删除临时音频：{debug_path}")
        finally:
            self.status = "idle"

    def _save_debug_wav(self, audio):
        # float32(-1~1) 转 int16 写入 wav，仅供调试回放
        path = os.path.join(
            tempfile.gettempdir(), f"yuyin_debug_{int(time.time())}.wav"
        )
        pcm = np.clip(audio, -1.0, 1.0)
        pcm = (pcm * 32767).astype(np.int16)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm.tobytes())
        print(f"🐞  调试音频已存：{path}")
        return path

    # ---------- 识别与输出 ----------

    def _transcribe(self, audio):
        try:
            segments, _ = self.model.transcribe(
                audio,
                language=LANGUAGE,
                beam_size=5,
                vad_filter=True,  # 过滤静音，识别更干净
            )
            text = "".join(seg.text for seg in segments).strip()
        except Exception as e:
            print(f"识别出错：{e}", file=sys.stderr)
            return

        if not text:
            print("没识别出内容。")
            return

        print(f"📝  {text}")
        self._beep("Glass")  # 「叮咚」：识别完成、文字已输出
        self._output(text)

    def _output(self, text):
        pyperclip.copy(text)
        if not AUTO_PASTE:
            print("（已复制到剪贴板，按 Cmd+V 粘贴）")
            return
        # 用剪贴板 + Cmd+V 输出，保证中文不乱码
        time.sleep(0.05)
        with self._kb.pressed(keyboard.Key.cmd):
            self._kb.press("v")
            self._kb.release("v")

    # ---------- 快捷键监听 ----------

    def on_press(self, key):
        if SHOW_KEYS:
            print(f"[按键] 你按下了：{key!r}")
        if key not in TRIGGER_KEYS:
            return
        # 长按时系统会连发 on_press，这里只在「真正按下的那一下」响应
        if self._key_down:
            return
        self._key_down = True

        if not self._recording:
            self.start_recording()
        else:
            # 识别可能耗时，放到后台线程，避免卡住按键监听
            threading.Thread(
                target=self.stop_recording_and_transcribe, daemon=True
            ).start()

    def on_release(self, key):
        if key in TRIGGER_KEYS:
            self._key_down = False

# ============ 屏幕浮动提示（像 Typeless 的悬浮小条，用 macOS 原生窗口实现）============

# pyobjc 已随 pynput 一起装好。若导入失败则自动退回「无窗口」模式。
try:
    import objc  # noqa: F401
    from Foundation import NSObject, NSTimer, NSMakeRect
    from AppKit import (
        NSApplication,
        NSPanel,
        NSColor,
        NSTextField,
        NSScreen,
        NSFont,
        NSBackingStoreBuffered,
        NSStatusWindowLevel,
        NSTextAlignmentCenter,
        NSApplicationActivationPolicyAccessory,
    )

    _NSWindowStyleMaskBorderless = 0
    _NSWindowStyleMaskNonactivatingPanel = 1 << 7
    _HAVE_COCOA = True
except Exception:
    _HAVE_COCOA = False


if _HAVE_COCOA:

    class OverlayController(NSObject):
        """屏幕底部中间的悬浮提示条；只读 typer.status，不抢焦点。"""

        def buildPanel(self):
            scr = NSScreen.mainScreen().frame()
            w, h = 240.0, 60.0
            x = (scr.size.width - w) / 2.0
            y = 150.0  # 距屏幕底部的高度
            rect = NSMakeRect(x, y, w, h)
            style = _NSWindowStyleMaskBorderless | _NSWindowStyleMaskNonactivatingPanel
            panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                rect, style, NSBackingStoreBuffered, False
            )
            panel.setLevel_(NSStatusWindowLevel)          # 浮在所有窗口之上
            panel.setOpaque_(False)
            panel.setBackgroundColor_(NSColor.clearColor())
            panel.setFloatingPanel_(True)
            panel.setHidesOnDeactivate_(False)
            panel.setIgnoresMouseEvents_(True)            # 鼠标点击穿透，不挡操作

            content = panel.contentView()
            content.setWantsLayer_(True)
            layer = content.layer()
            layer.setCornerRadius_(18.0)
            layer.setBackgroundColor_(
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    0.0, 0.0, 0.0, 0.82
                ).CGColor()
            )

            label = NSTextField.alloc().initWithFrame_(
                NSMakeRect(0, (h - 28) / 2.0, w, 28)
            )
            label.setBezeled_(False)
            label.setDrawsBackground_(False)
            label.setEditable_(False)
            label.setSelectable_(False)
            label.setAlignment_(NSTextAlignmentCenter)
            label.setTextColor_(NSColor.whiteColor())
            label.setFont_(NSFont.systemFontOfSize_(18.0))
            content.addSubview_(label)

            panel.orderOut_(None)  # 初始隐藏
            self.panel = panel
            self.label = label
            self.last = None

        def tick_(self, timer):
            status = getattr(self.typer, "status", "idle")
            if status == self.last:
                return
            self.last = status
            if status == "recording":
                self.label.setStringValue_(u"🔴  正在录音…")
                self.panel.orderFrontRegardless()
            elif status == "transcribing":
                self.label.setStringValue_(u"✍️  识别中…")
                self.panel.orderFrontRegardless()
            else:
                self.panel.orderOut_(None)


def _run_overlay(typer):
    import signal

    # 让 Ctrl+C 能退出（Cocoa 跑起来后默认拦不住）
    signal.signal(signal.SIGINT, lambda *a: os._exit(0))

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # 不占程序坞图标

    ctrl = OverlayController.alloc().init()
    ctrl.typer = typer
    ctrl.buildPanel()
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        0.1, ctrl, "tick:", None, True
    )
    app.run()


def main():
    typer = VoiceTyper()
    listener = keyboard.Listener(
        on_press=typer.on_press, on_release=typer.on_release
    )
    listener.start()

    print("=" * 48)
    print("  本地语音转文字已就绪")
    print("  按一下「右 Option」开始录音，再按一下结束并识别")
    print("  按 Ctrl+C 退出")
    print("=" * 48)

    if SHOW_OVERLAY and _HAVE_COCOA:
        try:
            _run_overlay(typer)  # 进入 Cocoa 主循环，显示浮动提示
            return
        except Exception as e:
            print(f"浮动提示启动失败，已退回无窗口模式：{e}", file=sys.stderr)

    try:
        listener.join()
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()
