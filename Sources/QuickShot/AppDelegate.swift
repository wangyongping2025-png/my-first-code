import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private let hotKey = HotKeyManager()
    private var overlay: OverlayController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        registerHotKey()

        // Best-effort permission nudge on first launch. We do not block startup;
        // the user can grant later and the prompts re-appear when needed.
        Permissions.warmUpIfNeeded()
    }

    // MARK: - Menu bar

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            // Template image so it adapts to light/dark menu bar.
            button.image = NSImage(systemSymbolName: "scissors", accessibilityDescription: "QuickShot")
            button.image?.isTemplate = true
        }
        rebuildMenu()
    }

    private func rebuildMenu() {
        let menu = NSMenu()

        let shotItem = NSMenuItem(title: "截图  (\(Preferences.shared.hotKey.displayString))",
                                  action: #selector(triggerCapture),
                                  keyEquivalent: "")
        shotItem.target = self
        menu.addItem(shotItem)

        let changeItem = NSMenuItem(title: "修改快捷键…",
                                    action: #selector(changeHotKey),
                                    keyEquivalent: "")
        changeItem.target = self
        menu.addItem(changeItem)

        menu.addItem(.separator())

        let loginItem = NSMenuItem(title: "开机自启",
                                   action: #selector(toggleLaunchAtLogin),
                                   keyEquivalent: "")
        loginItem.target = self
        loginItem.state = LaunchAtLogin.isEnabled ? .on : .off
        menu.addItem(loginItem)

        menu.addItem(.separator())

        let quitItem = NSMenuItem(title: "退出",
                                  action: #selector(NSApplication.terminate(_:)),
                                  keyEquivalent: "q")
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    // MARK: - Hot key

    private func registerHotKey() {
        hotKey.onTrigger = { [weak self] in
            self?.triggerCapture()
        }
        hotKey.register(Preferences.shared.hotKey)
    }

    @objc private func triggerCapture() {
        // Already capturing? Ignore re-triggers.
        guard overlay == nil else { return }

        guard Permissions.ensureScreenRecording() else {
            Permissions.openScreenRecordingSettings()
            return
        }

        let controller = OverlayController()
        controller.onFinish = { [weak self] in
            self?.overlay = nil   // release overlay + any retained images
        }
        overlay = controller
        controller.begin()
    }

    // MARK: - Preferences actions

    @objc private func changeHotKey() {
        HotKeyRecorderWindow.present { [weak self] newHotKey in
            guard let self = self, let newHotKey = newHotKey else { return }
            Preferences.shared.hotKey = newHotKey
            self.hotKey.register(newHotKey)
            self.rebuildMenu()
        }
    }

    @objc private func toggleLaunchAtLogin() {
        LaunchAtLogin.isEnabled.toggle()
        rebuildMenu()
    }
}
