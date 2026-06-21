import Foundation

/// Tiny UserDefaults-backed store. The only persisted setting is the hot key.
final class Preferences {
    static let shared = Preferences()

    private let defaults = UserDefaults.standard
    private let hotKeyKey = "QuickShot.hotKey"

    var hotKey: HotKeyCombo {
        get {
            guard let data = defaults.data(forKey: hotKeyKey),
                  let combo = try? JSONDecoder().decode(HotKeyCombo.self, from: data) else {
                return .default
            }
            return combo
        }
        set {
            if let data = try? JSONEncoder().encode(newValue) {
                defaults.set(data, forKey: hotKeyKey)
            }
        }
    }
}
