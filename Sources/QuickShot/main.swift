import Cocoa

// Entry point. We build the app programmatically (no storyboard / xib) to keep
// the bundle and footprint as small as possible.
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
// LSUIElement in Info.plist already keeps us out of the Dock, but set the
// activation policy explicitly so `swift run` (no bundle) also behaves.
app.setActivationPolicy(.accessory)
app.run()
