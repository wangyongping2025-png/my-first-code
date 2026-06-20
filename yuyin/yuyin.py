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

    # ---------- 录音 ----------

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

    def run(self):
        print("=" * 48)
        print(f"  本地语音转文字已就绪")
        print(f"  按一下「右 Option」开始录音，再按一下结束并识别")
        print(f"  按 Ctrl+C 退出")
        print("=" * 48)
        with keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        ) as listener:
            listener.join()


def main():
    try:
        VoiceTyper().run()
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()
