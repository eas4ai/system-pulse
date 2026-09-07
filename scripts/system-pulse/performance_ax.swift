import ApplicationServices
import Foundation

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}
let args = CommandLine.arguments
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
walk(app)
func press(_ key: String, _ value: String) {
    let matches = nodes.filter { (attr($0, key) as? String) == value }
    guard matches.count == 1,
          AXUIElementPerformAction(matches[0], kAXPressAction as CFString) == .success else {
        fail("No unique actionable \(key)=\(value)")
    }
}
let windows = children(app, "AXWindows")
switch args[2] {
case "prepare":
    guard windows.count == 1 else { fail("Expected one dashboard") }
    var size = CGSize(width: 1280, height: 880)
    guard let value = AXValueCreate(.cgSize, &size),
          AXUIElementSetAttributeValue(windows[0], kAXSizeAttribute as CFString, value) == .success else {
        fail("Could not set dashboard size")
    }
    press("AXIdentifier", "screen-tab:summary")
    AXUIElementSetAttributeValue(app, kAXFrontmostAttribute as CFString, kCFBooleanTrue)
case "close":
    guard windows.count == 1, let button = children(windows[0], "AXCloseButton").first,
          AXUIElementPerformAction(button, kAXPressAction as CFString) == .success else {
        fail("Could not close owned dashboard")
    }
case "quit": press("AXTitle", "Quit")
case "snapshot": break
default: fail("Unknown action")
}
var result: [[String: Any]] = []
for window in windows {
    guard let raw = attr(window, "AXSize"), CFGetTypeID(raw) == AXValueGetTypeID() else {
        fail("Missing native window size")
    }
    var size = CGSize.zero
    guard AXValueGetValue(unsafeBitCast(raw, to: AXValue.self), .cgSize, &size) else {
        fail("Invalid native window size")
    }
    let summary = nodes.contains { (attr($0, "AXIdentifier") as? String) == "screen:summary" }
    result.append(["width": size.width, "height": size.height, "screen": summary ? "Summary" : "Other"])
}
let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
