import Foundation
import ServiceManagement

/// Wraps the modern SMAppService login-item API (macOS 13+).
/// Only works when running as a signed .app bundle; harmless otherwise.
enum LaunchAtLogin {
    static var isEnabled: Bool {
        get {
            SMAppService.mainApp.status == .enabled
        }
        set {
            do {
                if newValue {
                    try SMAppService.mainApp.register()
                } else {
                    try SMAppService.mainApp.unregister()
                }
            } catch {
                NSLog("QuickShot: launch-at-login toggle failed: \(error)")
            }
        }
    }
}
