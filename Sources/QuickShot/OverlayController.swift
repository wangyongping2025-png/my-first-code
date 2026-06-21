import Cocoa

/// Owns the full-screen overlay session: one borderless window per display.
/// Created on hot-key press, torn down the instant the user confirms or cancels
/// so no window stays resident and the frozen screenshots are released.
final class OverlayController {
    var onFinish: (() -> Void)?

    private var windows: [NSWindow] = []
    private var views: [OverlayView] = []
    private var previousActiveApp: NSRunningApplication?
    private var finished = false

    func begin() {
        previousActiveApp = NSWorkspace.shared.frontmostApplication

        Capturer.captureAllDisplays { [weak self] shots in
            guard let self = self else { return }
            guard !shots.isEmpty else {
                // Capture produced nothing — almost always missing screen-
                // recording permission. Guide to Settings, then bail cleanly.
                if !Permissions.hasScreenRecording() {
                    Permissions.openScreenRecordingSettings()
                }
                self.onFinish?()
                return
            }
            self.showOverlays(for: shots)
        }
    }

    private func showOverlays(for shots: [DisplayShot]) {
        for shot in shots {
            let window = OverlayWindow(contentRect: shot.screen.frame,
                                       styleMask: .borderless,
                                       backing: .buffered,
                                       defer: false)
            window.isOpaque = false
            // Critical: we keep our own strong reference in `windows`. Letting
            // AppKit also release the window on close() causes an over-release
            // crash under ARC — which would kill the menu-bar app after the
            // first capture. Manage the lifetime ourselves.
            window.isReleasedWhenClosed = false
            window.backgroundColor = .clear
            window.level = NSWindow.Level(rawValue: Int(CGShieldingWindowLevel()))
            window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
            window.ignoresMouseEvents = false
            window.acceptsMouseMovedEvents = true
            window.hasShadow = false

            let view = OverlayView(frame: NSRect(origin: .zero, size: shot.screen.frame.size),
                                   shot: shot)
            view.controller = self
            window.contentView = view

            window.setFrame(shot.screen.frame, display: true)
            window.makeKeyAndOrderFront(nil)

            windows.append(window)
            views.append(view)
        }

        NSApp.activate(ignoringOtherApps: true)
        // Make the view under the current mouse the key responder so Enter/Esc work.
        windows.first?.makeFirstResponder(views.first)
    }

    /// Called by a view when the user confirms a selection.
    func confirm(selection globalCocoaRect: CGRect, from shot: DisplayShot) {
        Capturer.copyToPasteboard(selection: globalCocoaRect, from: shot)
        teardown()
    }

    /// Called by a view on Esc / cancel.
    func cancel() {
        teardown()
    }

    private func teardown() {
        guard !finished else { return }   // never tear down twice
        finished = true
        for window in windows { window.orderOut(nil) }
        windows.removeAll()
        views.removeAll()                 // drops OverlayViews and their DisplayShots
        previousActiveApp?.activate()
        onFinish?()                       // lets AppDelegate release this controller
    }
}
