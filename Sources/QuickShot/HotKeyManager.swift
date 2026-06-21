import Cocoa
import Carbon.HIToolbox

/// A keyboard shortcut described by a virtual key code and Carbon modifier mask.
struct HotKeyCombo: Codable, Equatable {
    var keyCode: UInt32        // kVK_* virtual key code
    var modifiers: UInt32      // Carbon modifier flags (controlKey, shiftKey, …)

    /// Default: Ctrl+Shift+S  (control — NOT command).
    static let `default` = HotKeyCombo(keyCode: UInt32(kVK_ANSI_S),
                                       modifiers: UInt32(controlKey | shiftKey))

    var displayString: String {
        var parts: [String] = []
        if modifiers & UInt32(controlKey)  != 0 { parts.append("⌃") }
        if modifiers & UInt32(optionKey)   != 0 { parts.append("⌥") }
        if modifiers & UInt32(shiftKey)    != 0 { parts.append("⇧") }
        if modifiers & UInt32(cmdKey)      != 0 { parts.append("⌘") }
        parts.append(KeyCodeNames.string(for: keyCode))
        return parts.joined()
    }
}

/// Registers a single global hot key through Carbon's RegisterEventHotKey.
/// Carbon remains the most reliable, lightweight way to grab a system-wide key
/// without an extra event-tap permission.
final class HotKeyManager {
    var onTrigger: (() -> Void)?

    private var hotKeyRef: EventHotKeyRef?
    private var eventHandler: EventHandlerRef?
    private let signature: OSType = 0x51534854  // 'QSHT'

    init() {
        installHandler()
    }

    deinit {
        unregister()
        if let eventHandler { RemoveEventHandler(eventHandler) }
    }

    private func installHandler() {
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard),
                                 eventKind: UInt32(kEventHotKeyPressed))
        let selfPtr = Unmanaged.passUnretained(self).toOpaque()
        InstallEventHandler(GetEventDispatcherTarget(), { _, event, userData -> OSStatus in
            guard let userData else { return noErr }
            let manager = Unmanaged<HotKeyManager>.fromOpaque(userData).takeUnretainedValue()
            var hkID = EventHotKeyID()
            GetEventParameter(event, EventParamName(kEventParamDirectObject),
                              EventParamType(typeEventHotKeyID), nil,
                              MemoryLayout<EventHotKeyID>.size, nil, &hkID)
            DispatchQueue.main.async { manager.onTrigger?() }
            return noErr
        }, 1, &spec, selfPtr, &eventHandler)
    }

    func register(_ combo: HotKeyCombo) {
        unregister()
        var ref: EventHotKeyRef?
        let hkID = EventHotKeyID(signature: signature, id: 1)
        let status = RegisterEventHotKey(combo.keyCode, combo.modifiers, hkID,
                                         GetEventDispatcherTarget(), 0, &ref)
        if status == noErr {
            hotKeyRef = ref
        } else {
            NSLog("QuickShot: failed to register hot key (status \(status))")
        }
    }

    func unregister() {
        if let hotKeyRef {
            UnregisterEventHotKey(hotKeyRef)
            self.hotKeyRef = nil
        }
    }
}
