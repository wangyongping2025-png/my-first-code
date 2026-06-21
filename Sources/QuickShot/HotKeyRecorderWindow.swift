import Cocoa
import Carbon.HIToolbox

/// A tiny modal panel that records the next key combination the user presses.
/// Requires at least one modifier so we never grab a bare key globally.
enum HotKeyRecorderWindow {

    static func present(completion: @escaping (HotKeyCombo?) -> Void) {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 360, height: 130),
                              styleMask: [.titled],
                              backing: .buffered, defer: false)
        window.title = "修改快捷键"
        window.center()
        window.isReleasedWhenClosed = false

        let label = NSTextField(wrappingLabelWithString:
            "按下新的快捷键\n(需包含 ⌃ ⌥ ⇧ ⌘ 至少一个修饰键)\n\n按 Esc 取消")
        label.alignment = .center
        label.frame = NSRect(x: 20, y: 20, width: 320, height: 90)
        window.contentView?.addSubview(label)

        NSApp.activate(ignoringOtherApps: true)

        var monitor: Any?
        func finish(_ combo: HotKeyCombo?) {
            if let monitor { NSEvent.removeMonitor(monitor) }
            window.orderOut(nil)
            NSApp.stopModal()
            completion(combo)
        }

        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            if Int(event.keyCode) == kVK_Escape {
                finish(nil)
                return nil
            }
            var carbonMods: UInt32 = 0
            let flags = event.modifierFlags
            if flags.contains(.control) { carbonMods |= UInt32(controlKey) }
            if flags.contains(.option)  { carbonMods |= UInt32(optionKey) }
            if flags.contains(.shift)   { carbonMods |= UInt32(shiftKey) }
            if flags.contains(.command) { carbonMods |= UInt32(cmdKey) }

            guard carbonMods != 0 else {
                NSSound.beep()      // bare key not allowed
                return nil
            }
            finish(HotKeyCombo(keyCode: UInt32(event.keyCode), modifiers: carbonMods))
            return nil
        }

        window.makeKeyAndOrderFront(nil)
        NSApp.runModal(for: window)
    }
}
