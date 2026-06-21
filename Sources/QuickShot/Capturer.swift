import Cocoa
import CoreGraphics
import ScreenCaptureKit

/// A frozen full-resolution snapshot of one display, taken the moment the
/// overlay appears. We crop from this rather than re-capturing, so the dim
/// overlay never ends up inside the screenshot.
struct DisplayShot {
    let screen: NSScreen
    let image: CGImage          // full-display pixels, top-left origin
}

/// Screen capture + clipboard delivery. Captures to memory only — never writes
/// a file, never shows a save dialog.
enum Capturer {

    // MARK: - Full-display capture (one per screen)

    /// Capture every screen up front, then hand the results back on the main
    /// thread. Prefers ScreenCaptureKit (macOS 14+); falls back to the legacy
    /// CGDisplayCreateImage path otherwise.
    static func captureAllDisplays(completion: @escaping ([DisplayShot]) -> Void) {
        let screens = NSScreen.screens

        if #available(macOS 14.0, *) {
            Task {
                var shots: [DisplayShot] = []
                let content = try? await SCShareableContent.excludingDesktopWindows(false,
                                                                                    onScreenWindowsOnly: true)
                for screen in screens {
                    guard let displayID = screen.displayID else { continue }
                    var image: CGImage?
                    if let scDisplay = content?.displays.first(where: { $0.displayID == displayID }) {
                        image = await captureSCK(scDisplay)
                    }
                    if image == nil { image = captureLegacy(displayID) }   // fallback
                    if let image { shots.append(DisplayShot(screen: screen, image: image)) }
                }
                let final = shots
                await MainActor.run { completion(final) }
            }
        } else {
            var shots: [DisplayShot] = []
            for screen in screens {
                guard let displayID = screen.displayID,
                      let image = captureLegacy(displayID) else { continue }
                shots.append(DisplayShot(screen: screen, image: image))
            }
            completion(shots)
        }
    }

    @available(macOS 14.0, *)
    private static func captureSCK(_ display: SCDisplay) async -> CGImage? {
        let filter = SCContentFilter(display: display, excludingWindows: [])
        let config = SCStreamConfiguration()
        config.width = display.width * scaleFactor(for: display)
        config.height = display.height * scaleFactor(for: display)
        config.showsCursor = false
        return try? await SCScreenshotManager.captureImage(contentFilter: filter,
                                                           configuration: config)
    }

    @available(macOS 14.0, *)
    private static func scaleFactor(for display: SCDisplay) -> Int {
        let match = NSScreen.screens.first { $0.displayID == display.displayID }
        return Int(match?.backingScaleFactor ?? 2)
    }

    /// Legacy / fallback full-display capture. CGDisplayCreateImage needs only
    /// the screen-recording permission and works back to macOS 10.x.
    private static func captureLegacy(_ displayID: CGDirectDisplayID) -> CGImage? {
        CGDisplayCreateImage(displayID)
    }

    // MARK: - Crop + deliver to clipboard

    /// Crop `selection` (global Cocoa points) out of `shot` and place the
    /// result on the general pasteboard as an image. Returns true on success.
    @discardableResult
    static func copyToPasteboard(selection: CGRect, from shot: DisplayShot) -> Bool {
        guard let cropped = crop(selection: selection, from: shot) else { return false }

        let rep = NSBitmapImageRep(cgImage: cropped)
        rep.size = NSSize(width: cropped.width, height: cropped.height)

        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()

        // Offer both PNG and TIFF so any paste target gets a usable image.
        var ok = false
        if let png = rep.representation(using: .png, properties: [:]) {
            ok = pasteboard.setData(png, forType: .png)
        }
        if let tiff = rep.tiffRepresentation {
            ok = pasteboard.setData(tiff, forType: .tiff) || ok
        }
        return ok
    }

    private static func crop(selection: CGRect, from shot: DisplayShot) -> CGImage? {
        let screen = shot.screen
        let image = shot.image

        // Selection → screen-local Cocoa points (bottom-left origin).
        let local = CGRect(x: selection.origin.x - screen.frame.origin.x,
                           y: selection.origin.y - screen.frame.origin.y,
                           width: selection.width,
                           height: selection.height)

        // Pixels-per-point for this capture (derive from the image itself so we
        // stay correct regardless of Retina scale).
        let scaleX = CGFloat(image.width) / screen.frame.width
        let scaleY = CGFloat(image.height) / screen.frame.height

        // Flip Y to the image's top-left origin and scale to pixels.
        let pixelRect = CGRect(
            x: (local.origin.x * scaleX).rounded(),
            y: ((screen.frame.height - local.origin.y - local.height) * scaleY).rounded(),
            width: (local.width * scaleX).rounded(),
            height: (local.height * scaleY).rounded()
        )

        let bounds = CGRect(x: 0, y: 0, width: image.width, height: image.height)
        let clipped = pixelRect.intersection(bounds)
        guard clipped.width >= 1, clipped.height >= 1 else { return nil }
        return image.cropping(to: clipped)
    }
}

extension NSScreen {
    /// The CoreGraphics display ID backing this screen.
    var displayID: CGDirectDisplayID? {
        deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? CGDirectDisplayID
    }
}
