import Cocoa
import CoreGraphics

/// One on-screen window's identity and frame (in global Cocoa points).
struct WindowInfo {
    let windowID: CGWindowID
    let frame: CGRect          // global Cocoa coordinates (bottom-left origin)
    let ownerPID: pid_t
    let ownerName: String
}

/// Primary smart-selection layer: enumerate visible windows via
/// CGWindowListCopyWindowInfo and find the top-most one under a point.
enum WindowEnumerator {

    /// All visible, on-screen windows, front-to-back (index 0 = frontmost).
    static func visibleWindows() -> [WindowInfo] {
        let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
        guard let raw = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
            return []
        }

        var result: [WindowInfo] = []
        for dict in raw {
            // Skip windows that are not normal app layers (menu bar, dock,
            // shadows, our own overlay, etc.). Layer 0 == regular windows.
            guard let layer = dict[kCGWindowLayer as String] as? Int, layer == 0 else { continue }
            guard let boundsDict = dict[kCGWindowBounds as String] as? [String: Any],
                  let cgBounds = CGRect(dictionaryRepresentation: boundsDict as CFDictionary) else { continue }
            // Ignore tiny/zero windows.
            guard cgBounds.width > 1, cgBounds.height > 1 else { continue }

            let pid = (dict[kCGWindowOwnerPID as String] as? pid_t) ?? 0
            let owner = (dict[kCGWindowOwnerName as String] as? String) ?? ""
            let wid = (dict[kCGWindowNumber as String] as? CGWindowID) ?? 0

            result.append(WindowInfo(windowID: wid,
                                     frame: Geometry.cocoaRect(fromCGGlobal: cgBounds),
                                     ownerPID: pid,
                                     ownerName: owner))
        }
        return result
    }

    /// Top-most window whose frame contains `point` (global Cocoa coords),
    /// skipping our own process so the overlay never selects itself.
    static func window(at point: CGPoint, excludingPID excluded: pid_t) -> WindowInfo? {
        for win in visibleWindows() where win.ownerPID != excluded {
            if win.frame.contains(point) { return win }
        }
        return nil
    }
}
