import Cocoa

/// The interactive selection surface for one display.
///
/// Coordinates here are *view-local* points (bottom-left origin), where the view
/// exactly covers its screen. We convert to global Cocoa / CoreGraphics only at
/// the edges (window & AX hit-testing, final crop).
final class OverlayView: NSView {
    weak var controller: OverlayController?

    private let shot: DisplayShot
    private let nsImage: NSImage
    private let pixelScale: CGFloat          // image pixels per point
    private let selfPID = ProcessInfo.processInfo.processIdentifier

    // Smart-hover candidate (window / AX element under cursor), before commit.
    private var candidateRect: CGRect?
    // The committed, editable selection.
    private var committedRect: CGRect?

    private enum DragMode: Equatable {
        case none, creating, moving, resizing(Handle)
    }
    private var dragMode: DragMode = .none
    private var dragStart: CGPoint = .zero
    private var rectAtDragStart: CGRect = .zero
    private var didDrag = false

    private let handleSize: CGFloat = 8
    private let clickThreshold: CGFloat = 4

    init(frame: NSRect, shot: DisplayShot) {
        self.shot = shot
        self.nsImage = NSImage(cgImage: shot.image, size: frame.size)
        self.pixelScale = CGFloat(shot.image.width) / max(frame.width, 1)
        super.init(frame: frame)
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override var acceptsFirstResponder: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    // MARK: - Tracking

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        trackingAreas.forEach(removeTrackingArea)
        addTrackingArea(NSTrackingArea(rect: bounds,
                                       options: [.activeAlways, .mouseMoved, .inVisibleRect],
                                       owner: self, userInfo: nil))
    }

    // MARK: - Coordinate conversion

    private func toLocal(_ globalCocoa: CGRect) -> CGRect {
        globalCocoa.offsetBy(dx: -shot.screen.frame.origin.x, dy: -shot.screen.frame.origin.y)
    }

    private func globalCocoaPoint(_ local: CGPoint) -> CGPoint {
        CGPoint(x: local.x + shot.screen.frame.origin.x,
                y: local.y + shot.screen.frame.origin.y)
    }

    // MARK: - Smart hover

    private func updateCandidate(at local: CGPoint) {
        let globalCocoa = globalCocoaPoint(local)
        let cg = Geometry.cgPoint(fromCocoaGlobal: globalCocoa)

        var found: CGRect?
        // Best-effort sub-element first; silently ignore when unavailable.
        if let axGlobal = AXElementFinder.elementFrame(atCGPoint: cg) {
            found = toLocal(axGlobal)
        }
        // Fall back to whole-window selection.
        if found == nil, let win = WindowEnumerator.window(at: globalCocoa, excludingPID: selfPID) {
            found = toLocal(win.frame)
        }

        // Keep only the part on this screen; drop degenerate hits.
        if let f = found?.intersection(bounds), f.width > 4, f.height > 4 {
            candidateRect = f
        } else {
            candidateRect = nil
        }
        needsDisplay = true
    }

    // MARK: - Mouse

    override func mouseMoved(with event: NSEvent) {
        // On multi-monitor setups, make the window under the cursor the key
        // window so keyboard (Enter/Esc) acts on the screen you're pointing at.
        if window?.isKeyWindow == false {
            window?.makeKey()
            window?.makeFirstResponder(self)
        }
        guard dragMode == .none, committedRect == nil else { return }
        updateCandidate(at: convert(event.locationInWindow, from: nil))
    }

    override func mouseDown(with event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        didDrag = false
        dragStart = p

        if let rect = committedRect {
            if event.clickCount >= 2, rect.contains(p) {
                confirm()
                return
            }
            if let handle = handleHit(at: p, for: rect) {
                dragMode = .resizing(handle)
                rectAtDragStart = rect
                return
            }
            if rect.contains(p) {
                dragMode = .moving
                rectAtDragStart = rect
                return
            }
            // Click outside the committed rect → start a fresh selection.
            committedRect = nil
        }
        dragMode = .creating
    }

    override func mouseDragged(with event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        if hypot(p.x - dragStart.x, p.y - dragStart.y) > clickThreshold { didDrag = true }

        switch dragMode {
        case .creating:
            committedRect = normalizedRect(from: dragStart, to: p).intersection(bounds)
        case .moving:
            let dx = p.x - dragStart.x
            let dy = p.y - dragStart.y
            committedRect = clampToBounds(rectAtDragStart.offsetBy(dx: dx, dy: dy))
        case .resizing(let handle):
            committedRect = resize(rectAtDragStart, handle: handle,
                                   dx: p.x - dragStart.x, dy: p.y - dragStart.y)
                .intersection(bounds)
        case .none:
            break
        }
        needsDisplay = true
    }

    override func mouseUp(with event: NSEvent) {
        if dragMode == .creating {
            if didDrag, let r = committedRect, r.width > clickThreshold, r.height > clickThreshold {
                // keep the dragged rectangle
            } else {
                // A click (no real drag) → commit the hovered candidate, if any.
                committedRect = candidateRect
            }
        }
        dragMode = .none
        candidateRect = nil
        needsDisplay = true
    }

    // MARK: - Keyboard

    override func keyDown(with event: NSEvent) {
        switch Int(event.keyCode) {
        case 53:                 // Esc
            controller?.cancel()
        case 36, 76:             // Return / keypad Enter
            confirm()
        default:
            super.keyDown(with: event)
        }
    }

    private func confirm() {
        guard let rect = committedRect ?? candidateRect,
              rect.width >= 1, rect.height >= 1 else {
            controller?.cancel()
            return
        }
        let globalCocoa = rect.offsetBy(dx: shot.screen.frame.origin.x,
                                        dy: shot.screen.frame.origin.y)
        controller?.confirm(selection: globalCocoa, from: shot)
    }

    // MARK: - Resize math

    private func resize(_ start: CGRect, handle: Handle, dx: CGFloat, dy: CGFloat) -> CGRect {
        var minX = start.minX, maxX = start.maxX
        var minY = start.minY, maxY = start.maxY
        if handle.affectsLeft   { minX += dx }
        if handle.affectsRight  { maxX += dx }
        if handle.affectsBottom { minY += dy }
        if handle.affectsTop    { maxY += dy }
        return CGRect(x: min(minX, maxX), y: min(minY, maxY),
                      width: abs(maxX - minX), height: abs(maxY - minY))
    }

    private func normalizedRect(from a: CGPoint, to b: CGPoint) -> CGRect {
        CGRect(x: min(a.x, b.x), y: min(a.y, b.y),
               width: abs(a.x - b.x), height: abs(a.y - b.y))
    }

    private func clampToBounds(_ rect: CGRect) -> CGRect {
        var r = rect
        if r.minX < 0 { r.origin.x = 0 }
        if r.minY < 0 { r.origin.y = 0 }
        if r.maxX > bounds.width  { r.origin.x = bounds.width  - r.width }
        if r.maxY > bounds.height { r.origin.y = bounds.height - r.height }
        return r
    }

    // MARK: - Handles

    private func handleCenters(for rect: CGRect) -> [(Handle, CGPoint)] {
        [
            (.bottomLeft,  CGPoint(x: rect.minX, y: rect.minY)),
            (.bottom,      CGPoint(x: rect.midX, y: rect.minY)),
            (.bottomRight, CGPoint(x: rect.maxX, y: rect.minY)),
            (.left,        CGPoint(x: rect.minX, y: rect.midY)),
            (.right,       CGPoint(x: rect.maxX, y: rect.midY)),
            (.topLeft,     CGPoint(x: rect.minX, y: rect.maxY)),
            (.top,         CGPoint(x: rect.midX, y: rect.maxY)),
            (.topRight,    CGPoint(x: rect.maxX, y: rect.maxY))
        ]
    }

    private func handleHit(at p: CGPoint, for rect: CGRect) -> Handle? {
        let tol = handleSize
        for (handle, center) in handleCenters(for: rect) {
            if abs(p.x - center.x) <= tol, abs(p.y - center.y) <= tol { return handle }
        }
        return nil
    }

    // MARK: - Drawing

    override func draw(_ dirtyRect: NSRect) {
        // Frozen screenshot.
        nsImage.draw(in: bounds, from: .zero, operation: .copy, fraction: 1)
        // Dim the whole screen.
        NSColor(white: 0, alpha: 0.45).setFill()
        bounds.fill()

        guard let active = committedRect ?? candidateRect else { return }

        // Re-draw the selected region at full brightness.
        nsImage.draw(in: active, from: active, operation: .sourceOver, fraction: 1)

        // Selection border.
        let border = NSBezierPath(rect: active)
        border.lineWidth = 1.5
        NSColor.controlAccentColor.setStroke()
        border.stroke()

        // Handles only on a committed, idle selection.
        if committedRect != nil, dragMode == .none {
            NSColor.white.setFill()
            NSColor.controlAccentColor.setStroke()
            for (_, center) in handleCenters(for: active) {
                let r = NSRect(x: center.x - handleSize / 2, y: center.y - handleSize / 2,
                               width: handleSize, height: handleSize)
                let path = NSBezierPath(ovalIn: r)
                path.fill()
                path.stroke()
            }
        }

        drawSizeLabel(for: active)
    }

    private func drawSizeLabel(for rect: CGRect) {
        let wPx = Int((rect.width * pixelScale).rounded())
        let hPx = Int((rect.height * pixelScale).rounded())
        let text = "\(wPx) × \(hPx)"

        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .medium),
            .foregroundColor: NSColor.white
        ]
        let size = (text as NSString).size(withAttributes: attrs)
        let padding: CGFloat = 5
        let boxW = size.width + padding * 2
        let boxH = size.height + padding * 2

        // Prefer just above the selection; flip below if no room.
        var origin = CGPoint(x: rect.minX, y: rect.maxY + 6)
        if origin.y + boxH > bounds.height { origin.y = rect.minY - boxH - 6 }
        if origin.x + boxW > bounds.width  { origin.x = bounds.width - boxW }
        if origin.x < 0 { origin.x = 0 }
        if origin.y < 0 { origin.y = rect.maxY + 6 }

        let box = NSRect(origin: origin, size: CGSize(width: boxW, height: boxH))
        NSColor(white: 0, alpha: 0.7).setFill()
        NSBezierPath(roundedRect: box, xRadius: 4, yRadius: 4).fill()
        (text as NSString).draw(at: CGPoint(x: origin.x + padding, y: origin.y + padding),
                                withAttributes: attrs)
    }

    // MARK: - Cursor

    override func resetCursorRects() {
        addCursorRect(bounds, cursor: .crosshair)
    }
}

/// The eight resize handles around a selection.
enum Handle: Equatable {
    case topLeft, top, topRight, left, right, bottomLeft, bottom, bottomRight

    var affectsLeft: Bool   { self == .topLeft || self == .left || self == .bottomLeft }
    var affectsRight: Bool  { self == .topRight || self == .right || self == .bottomRight }
    var affectsTop: Bool    { self == .topLeft || self == .top || self == .topRight }
    var affectsBottom: Bool { self == .bottomLeft || self == .bottom || self == .bottomRight }
}
