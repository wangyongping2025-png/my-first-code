# QuickShot —— macOS 本地截图小工具

一个纯单机、菜单栏常驻的极简截图工具。**截图直接进剪贴板**,粘贴即用,不写磁盘、不留历史、无任何云服务与网络上传。

用 Swift 原生开发,无 Electron / 浏览器内核。平时只有一个菜单栏图标,按下快捷键才创建覆盖层,用完立即销毁、释放内存。

---

## 功能

- 全局快捷键唤起(默认 **⌃⇧S**,即 Control+Shift+S,**不是** Cmd),可在菜单栏修改。
- 半透明暗化全屏覆盖层(类似系统截图)。
- **窗口级智能识别**:鼠标悬停自动高亮该窗口,回车即整窗截图。
- **子区域识别**(best-effort,基于 Accessibility):能拿到 UI 元素就预选;微信/浏览器/Electron 等拿不到时,静默回退到窗口级 + 手动框选。
- 手动拖拽矩形框选;选区四边四角有手柄,可拖拽改大小、可整体拖动;实时显示像素尺寸。
- 回车 / 双击选区确认 → 进剪贴板;Esc 取消。
- 菜单栏极简:截图 / 修改快捷键 / 开机自启 / 退出。

---

## 构建与运行

需要 macOS 13+ 与 Xcode 命令行工具(`xcode-select --install`)。ScreenCaptureKit 路径在 macOS 14+ 生效,13 上自动回退到 `CGDisplayCreateImage`。

```bash
# 在项目根目录
./build_app.sh        # 编译并打包出 QuickShot.app(release,含 ad-hoc 签名)
open QuickShot.app    # 运行;图标出现在菜单栏
```

也可以直接用 SwiftPM 编译可执行文件(但菜单栏 LSUIElement 行为依赖 .app bundle,推荐用上面的脚本):

```bash
swift build -c release
```

> 用 Xcode 打开:`File ▸ Open…` 选择项目根目录(含 `Package.swift`)即可,Xcode 会识别为 Swift Package。命令行 `./build_app.sh` 是最简路径。

---

## 授权(首次必做)

首次运行会弹窗引导。需要两项系统权限:

1. **屏幕录制**(截屏必需)
   系统设置 ▸ 隐私与安全性 ▸ 屏幕录制 → 勾选 QuickShot。
2. **辅助功能**(窗口/控件识别,可选但推荐)
   系统设置 ▸ 隐私与安全性 ▸ 辅助功能 → 勾选 QuickShot。

弹窗里的按钮会直接跳转到对应设置面板。**授权后请退出并重新打开 QuickShot**(macOS 对屏幕录制权限的生效通常需要重启 app)。

---

## 快捷键

- 默认:**⌃⇧S**(Control + Shift + S)。
- 修改:菜单栏图标 ▸ 修改快捷键…,按下新组合键(需含至少一个修饰键)。

---

## 交互速查

| 操作 | 效果 |
|------|------|
| 移动鼠标 | 高亮悬停窗口/控件并预选,显示像素尺寸 |
| 按住拖拽 | 自定义矩形框选 |
| 拖动手柄 | 调整选区大小 |
| 选区内拖动 | 整体移动选区 |
| 回车 / 双击选区 | 截图 → 剪贴板,结束 |
| 单击某窗口 | 把该窗口选区设为可编辑选区 |
| Esc | 取消,不截图 |

---

## 设计取舍 / 自检

- **不写磁盘**:截图只经 `NSPasteboard`(PNG + TIFF),全程无文件、无保存对话框、无历史。
- **轻量常驻**:平时只有菜单栏 item,无窗口、无定时器;覆盖层与冻结截图在确认/取消后即刻释放。
- **无网络**:代码不含任何网络调用。
- 不含录屏、OCR、标注、云同步等额外功能。

---

## 项目结构

```
Package.swift                  SwiftPM 配置
build_app.sh                   编译 + 打包 .app 脚本
Resources/Info.plist           LSUIElement、权限文案
Sources/QuickShot/
  main.swift                   入口(.accessory 激活策略)
  AppDelegate.swift            菜单栏、权限引导、快捷键接线
  HotKeyManager.swift          Carbon RegisterEventHotKey 全局快捷键
  HotKeyRecorderWindow.swift   修改快捷键的录制面板
  KeyCodeNames.swift           键码 → 显示名
  Preferences.swift            快捷键持久化(UserDefaults)
  LaunchAtLogin.swift          SMAppService 开机自启
  Permissions.swift            屏幕录制 / 辅助功能 权限与设置跳转
  Geometry.swift               CG(左上) ↔ Cocoa(左下) 坐标换算
  WindowEnumerator.swift       CGWindowList 窗口级识别
  AXElementFinder.swift        Accessibility 子区域识别(best-effort)
  Capturer.swift               ScreenCaptureKit / 回退捕获 + 裁剪 + 剪贴板
  OverlayController.swift      覆盖层会话(每屏一窗),用完销毁
  OverlayView.swift            选区交互:高亮、框选、手柄、尺寸标注
```
