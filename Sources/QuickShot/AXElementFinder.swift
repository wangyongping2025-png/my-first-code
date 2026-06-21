import Cocoa
import ApplicationServices

/// Second, best-effort smart-selection layer: ask the Accessibility API for the
/// UI element directly under the cursor and return its bounds.
///
/// Many apps (WeChat, browsers, Electron) expose no useful AX tree. In those
/// cases we simply return nil and the caller silently falls back to window-level
/// selection + manual drag. No errors, no blocking.
enum AXElementFinder {
    private static let systemWide = AXUIElementCreateSystemWide()

    /// Frame (global Cocoa points) of the deepest AX element at a CG-global,
    /// top-left point — or nil if unavailable.
    static func elementFrame(atCGPoint cgPoint: CGPoint) -> CGRect? {
        guard AXIsProcessTrusted() else { return nil }

        var element: AXUIElement?
        let hit = AXUIElementCopyElementAtPosition(systemWide,
                                                   Float(cgPoint.x),
                                                   Float(cgPoint.y),
                                                   &element)
        guard hit == .success, let element else { return nil }

        guard let frame = frame(of: element) else { return nil }
        // Reject degenerate or absurdly large hits (e.g. the whole window when
        // AX gives nothing finer) — those add no value over window selection.
        guard frame.width > 4, frame.height > 4 else { return nil }
        return Geometry.cocoaRect(fromCGGlobal: frame)
    }

    private static func frame(of element: AXUIElement) -> CGRect? {
        var posValue: CFTypeRef?
        var sizeValue: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, kAXPositionAttribute as CFString, &posValue) == .success,
              AXUIElementCopyAttributeValue(element, kAXSizeAttribute as CFString, &sizeValue) == .success
        else { return nil }

        var point = CGPoint.zero
        var size = CGSize.zero
        guard AXValueGetValue(posValue as! AXValue, .cgPoint, &point),
              AXValueGetValue(sizeValue as! AXValue, .cgSize, &size)
        else { return nil }

        return CGRect(origin: point, size: size)
    }
}
