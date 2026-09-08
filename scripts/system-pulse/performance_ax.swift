import ApplicationServices
import Foundation

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}
let args = CommandLine.arguments
let session = CGSessionCopyCurrentDictionary() as? [String: Any] ?? [:]
if session["CGSSessionScreenIsLocked"] as? Bool == true {
    fail("The Mac session is locked; unlock it before native measurements")
}
guard args.count == 3, let pid = Int32(args[1]), pid > 0, AXIsProcessTrusted() else {
    fail("Expected owned PID, action and Accessibility permission")
}
let app = AXUIElementCreateApplication(pid)
AXUIElementSetMessagingTimeout(app, 2)
AXUIElementSetAttributeValue(app, "AXEnhancedUserInterface" as CFString, kCFBooleanTrue)
AXUIElementSetAttributeValue(app, "AXManualAccessibility" as CFString, kCFBooleanTrue)
func attr(_ node: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(node, name as CFString, &value) == .success ? value : nil
}
func children(_ node: AXUIElement, _ name: String) -> [AXUIElement] {
    guard let value = attr(node, name) else { return [] }
    if CFGetTypeID(value) == AXUIElementGetTypeID() {
        return [unsafeBitCast(value, to: AXUIElement.self)]
    }
    return (value as? [AnyObject] ?? []).filter { CFGetTypeID($0) == AXUIElementGetTypeID() }
        .map { unsafeBitCast($0, to: AXUIElement.self) }
}
var nodes: [AXUIElement] = []
func walk(_ node: AXUIElement, _ depth: Int = 0) {
    guard depth < 30, nodes.count < 3000, !nodes.contains(where: { CFEqual($0, node) }) else { return }
    nodes.append(node)
    for key in ["AXChildren", "AXWindows", "AXMenuBar", "AXExtrasMenuBar"] {
        for child in children(node, key) { walk(child, depth + 1) }
    }
}
for key in ["AXWindows", "AXMenuBar", "AXExtrasMenuBar"] {
    for node in children(app, key) { walk(node) }
}
func press(_ key: String, _ value: String) {
    let matches = nodes.filter { (attr($0, key) as? String) == value }
    guard matches.count == 1,
          AXUIElementPerformAction(matches[0], kAXPressAction as CFString) == .success else {
        fail("No unique actionable \(key)=\(value)")
    }
}
let windows = children(app, "AXWindows")
func nativeBounds() -> [CGRect] {
    let info = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                        kCGNullWindowID) as? [[String: Any]] ?? []
    return info.filter {
        ($0[kCGWindowOwnerPID as String] as? Int32) == pid &&
        ($0[kCGWindowLayer as String] as? Int) == 0
    }.compactMap {
        guard let bounds = $0[kCGWindowBounds as String] as? NSDictionary else { return nil }
        return CGRect(dictionaryRepresentation: bounds)
    }
}
switch args[2] {
case "prepare":
    guard windows.count == 1, nativeBounds().count == 1 else { fail("Expected one dashboard") }
    AXUIElementSetAttributeValue(app, kAXFrontmostAttribute as CFString, kCFBooleanTrue)
    press("AXIdentifier", "screen-tab:summary")
    let bounds = nativeBounds()[0]
    let start = CGPoint(x: bounds.maxX - 2, y: bounds.maxY - 2)
    let end = CGPoint(x: bounds.minX + 1280 - 2, y: bounds.minY + 880 - 2)
    // GPUI's accessibility root does not implement the native size setter.
    // Resize the owned window through the same corner drag a person uses.
    for (type, point) in [(CGEventType.mouseMoved, start), (.leftMouseDown, start),
                          (.leftMouseDragged, end), (.leftMouseUp, end)] {
        guard let event = CGEvent(mouseEventSource: nil, mouseType: type,
                                  mouseCursorPosition: point, mouseButton: .left) else {
            fail("Could not create native resize event")
        }
        event.post(tap: .cghidEventTap)
        Thread.sleep(forTimeInterval: 0.1)
    }
case "close":
    guard windows.count == 1, let button = children(windows[0], "AXCloseButton").first,
          AXUIElementPerformAction(button, kAXPressAction as CFString) == .success else {
        fail("Could not close owned dashboard")
    }
case "quit":
    press("AXTitle", "Quit")
    print("[]")
    exit(0)
case "snapshot": break
default: fail("Unknown action")
}
var result: [[String: Any]] = []
for bounds in nativeBounds() {
    let summary = nodes.contains { (attr($0, "AXIdentifier") as? String) == "screen:summary" }
    result.append(["width": bounds.width, "height": bounds.height, "screen": summary ? "Summary" : "Other"])
}
let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
