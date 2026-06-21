import Cocoa
import CoreGraphics
import ApplicationServices

/// Screen-recording + accessibility permission helpers, plus deep links into
/// the right System Settings panes.
enum Permissions {

    // MARK: Screen recording (required for capture)

    /// Returns true if screen recording is already authorized. Does NOT prompt.
    static func hasScreenRecording() -> Bool {
        CGPreflightScreenCaptureAccess()
    }

    /// Ensures access, triggering the system prompt the first time.
    @discardableResult
    static func ensureScreenRecording() -> Bool {
        if CGPreflightScreenCaptureAccess() { return true }
        // This call shows the system prompt once; subsequent calls just return.
        return CGRequestScreenCaptureAccess()
    }

    // MARK: Accessibility (required for window/control identification)

    static func hasAccessibility() -> Bool {
        AXIsProcessTrusted()
    }

    /// Prompts for accessibility access if not yet granted.
    @discardableResult
    static func ensureAccessibility() -> Bool {
        let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        return AXIsProcessTrustedWithOptions(opts)
    }

    // MARK: First-launch nudge

    static func warmUpIfNeeded() {
        var missing: [String] = []
        if !hasScreenRecording() { missing.append("屏幕录制") }
        if !hasAccessibility()  { missing.append("辅助功能") }
        guard !missing.isEmpty else { return }

        let alert = NSAlert()
        alert.messageText = "QuickShot 需要权限"
        alert.informativeText = """
        为了截图与窗口识别,QuickShot 需要以下权限:
        • 屏幕录制(截屏必需)
        • 辅助功能(窗口/控件识别,可选但推荐)

        缺少: \(missing.joined(separator: "、"))

        请在系统设置中开启,然后回到本应用按快捷键即可使用。
        """
        alert.addButton(withTitle: "打开「屏幕录制」设置")
        alert.addButton(withTitle: "打开「辅助功能」设置")
        alert.addButton(withTitle: "稍后")
        switch alert.runModal() {
        case .alertFirstButtonReturn:  openScreenRecordingSettings()
        case .alertSecondButtonReturn: openAccessibilitySettings()
        default: break
        }
    }

    // MARK: Deep links

    static func openScreenRecordingSettings() {
        open("x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture")
    }

    static func openAccessibilitySettings() {
        open("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
    }

    private static func open(_ urlString: String) {
        if let url = URL(string: urlString) {
            NSWorkspace.shared.open(url)
        }
    }
}
