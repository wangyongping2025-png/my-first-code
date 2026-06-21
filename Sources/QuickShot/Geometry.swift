import Cocoa

/// Coordinate-system helpers.
///
/// - CoreGraphics window/AX APIs use a *global, top-left* origin (y grows down),
///   measured from the primary display's top-left corner.
/// - Cocoa (NSScreen / NSWindow / NSView) uses a *global, bottom-left* origin
///   (y grows up), measured from the primary display's bottom-left corner.
///
/// We standardise on "global Cocoa points" inside the overlay and convert as
/// needed at the boundaries.
enum Geometry {
    /// Height of the primary display (the one whose origin is (0,0)). The flip
    /// pivots around this value.
    static var primaryHeight: CGFloat {
        // screens[0] is always the primary (menu-bar) screen.
        NSScreen.screens.first?.frame.height ?? 0
    }

    /// Convert a CoreGraphics top-left global rect to a Cocoa bottom-left global rect.
    static func cocoaRect(fromCGGlobal rect: CGRect) -> CGRect {
        CGRect(x: rect.origin.x,
               y: primaryHeight - rect.origin.y - rect.height,
               width: rect.width,
               height: rect.height)
    }

    /// Convert a Cocoa bottom-left global point to a CoreGraphics top-left point.
    static func cgPoint(fromCocoaGlobal point: CGPoint) -> CGPoint {
        CGPoint(x: point.x, y: primaryHeight - point.y)
    }
}
