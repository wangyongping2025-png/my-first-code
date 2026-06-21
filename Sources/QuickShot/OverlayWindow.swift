import Cocoa

/// Borderless windows refuse key/main status by default, which would stop the
/// overlay from receiving Enter/Esc. Override so the selection view can be first
/// responder and handle keyboard input.
final class OverlayWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}
