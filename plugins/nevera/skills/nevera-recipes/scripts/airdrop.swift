// Opens the AirDrop window with a file and waits for the user to pick a device.
//
//     swift airdrop.swift <file>
//
// Exits 0 when the Mac reports the send as done. Any other exit means it wasn't,
// and deliver.py falls back to the Finder. The phone still confirms the arrival:
// didShareItems is only what the Mac knows.

import AppKit

// Time to pick a device. deliver.py gives up a little after this.
let waitSeconds = 240.0

func finish(_ code: Int32, _ message: String) -> Never {
    print(message)
    fflush(stdout)
    exit(code)
}

final class Watcher: NSObject, NSSharingServiceDelegate {
    func sharingService(_ service: NSSharingService, didShareItems items: [Any]) {
        finish(0, "AirDrop reported the send as done")
    }

    func sharingService(
        _ service: NSSharingService, didFailToShareItems items: [Any], error: Error
    ) {
        finish(1, "AirDrop didn't send it: \(error.localizedDescription)")
    }
}

guard CommandLine.arguments.count == 2 else {
    finish(2, "Usage: swift airdrop.swift <file>")
}

let file = URL(fileURLWithPath: CommandLine.arguments[1])
let app = NSApplication.shared

// Accessory keeps it out of the Dock while it can still show a window.
app.setActivationPolicy(.accessory)

guard let service = NSSharingService(named: .sendViaAirDrop) else {
    finish(3, "This Mac offers no AirDrop service")
}
guard service.canPerform(withItems: [file]) else {
    finish(3, "AirDrop can't send this file")
}

// The service keeps a weak reference to its delegate.
let watcher = Watcher()
service.delegate = watcher
service.perform(withItems: [file])

DispatchQueue.main.asyncAfter(deadline: .now() + waitSeconds) {
    finish(4, "No device picked in \(Int(waitSeconds)) seconds")
}

// The window only lives while the event loop runs.
app.activate(ignoringOtherApps: true)
app.run()
