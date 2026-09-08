import Foundation
import ApplicationServices
let args = CommandLine.arguments
func fail(_ message: String) -> Never { FileHandle.standardError.write(Data((message+"\n").utf8)); exit(1) }
let session = CGSessionCopyCurrentDictionary() as? [String: Any] ?? [:]
if session["CGSSessionScreenIsLocked"] as? Bool == true { fail("The Mac session is locked; unlock it before native observations") }
guard args.count >= 2, let pid = Int32(args[1]), pid > 0, AXIsProcessTrusted() else { fail("PID and accessibility trust required") }
let app = AXUIElementCreateApplication(pid)
AXUIElementSetMessagingTimeout(app, 2)
AXUIElementSetAttributeValue(app, "AXEnhancedUserInterface" as CFString, kCFBooleanTrue)
AXUIElementSetAttributeValue(app, "AXManualAccessibility" as CFString, kCFBooleanTrue)
func attr(_ node: AXUIElement, _ name: String) -> AnyObject? {
 var value: CFTypeRef?
 return AXUIElementCopyAttributeValue(node, name as CFString, &value) == .success ? value : nil
}
func text(_ node: AXUIElement, _ name: String) -> String { attr(node,name) as? String ?? "" }
func elements(_ node: AXUIElement, _ name: String) -> [AXUIElement] {
 guard let value = attr(node,name) else { return [] }
 if CFGetTypeID(value) == AXUIElementGetTypeID() { return [unsafeBitCast(value, to: AXUIElement.self)] }
 return (value as? [AnyObject] ?? []).filter { CFGetTypeID($0) == AXUIElementGetTypeID() }.map { unsafeBitCast($0,to: AXUIElement.self) }
}
var nodes: [AXUIElement] = []
var rows: [[String:Any]] = []
func walk(_ node: AXUIElement, _ depth: Int) {
 guard depth < 30, nodes.count < 3000, !nodes.contains(where: { CFEqual($0,node) }) else { return }
 let index = nodes.count
 nodes.append(node)
 var row: [String:Any] = ["index":index,"depth":depth]
 for name in ["AXRole","AXSubrole","AXTitle","AXDescription","AXIdentifier","AXHelp"] { row[name] = text(node,name) }
 if let value = attr(node,"AXValue") as? String { row["AXValue"] = value }
 if let value = attr(node,"AXValue") as? NSNumber { row["AXValue"] = value }
 if let position = attr(node,"AXPosition"), let size = attr(node,"AXSize"),
    CFGetTypeID(position) == AXValueGetTypeID(), CFGetTypeID(size) == AXValueGetTypeID() {
  var point = CGPoint.zero
  var dimensions = CGSize.zero
  if AXValueGetValue(unsafeBitCast(position, to: AXValue.self), .cgPoint, &point),
     AXValueGetValue(unsafeBitCast(size, to: AXValue.self), .cgSize, &dimensions) {
   row["bounds"] = [point.x, point.y, dimensions.width, dimensions.height]
  }
 }
 var actions: CFArray?
 AXUIElementCopyActionNames(node,&actions)
 row["actions"] = actions as? [String] ?? []
 rows.append(row)
 for name in ["AXChildren","AXWindows","AXMenuBar","AXExtrasMenuBar"] { for child in elements(node,name) { walk(child,depth+1) } }
}
for name in ["AXWindows","AXMenuBar","AXExtrasMenuBar"] { for node in elements(app,name) { walk(node,0) } }
let mode = args.count > 2 ? args[2] : "snapshot"
var result: [String:Any] = ["pid":pid,"windows":elements(app,"AXWindows").count,"rows":rows]
if mode == "close" {
 let windows = elements(app,"AXWindows")
 guard windows.count == 1, let button = elements(windows[0],"AXCloseButton").first else { fail("Expected one owned window with close button") }
 let code = AXUIElementPerformAction(button,kAXPressAction as CFString)
 result["action_return"] = code.rawValue
 guard code == .success else { fail("Native close failed: \(code)") }
} else if mode == "press-id" || mode == "press-title" {
 guard args.count == 4 else { fail("Selector value required") }
 let key = mode == "press-id" ? "AXIdentifier" : "AXTitle"
 let matches = rows.filter { ($0[key] as? String) == args[3] && ($0["actions"] as? [String] ?? []).contains("AXPress") }
 guard matches.count == 1, let index = matches[0]["index"] as? Int else { fail("Expected unique actionable selector: \(args[3]); matches=\(matches.count)") }
 let code = AXUIElementPerformAction(nodes[index],kAXPressAction as CFString)
 result["action_return"] = code.rawValue
 guard code == .success else { fail("Native press failed: \(code)") }
} else if mode == "resize" {
 guard args.count == 5, let width = Double(args[3]), let height = Double(args[4]),
       width >= 960, width <= 2560, height >= 640, height <= 1600 else { fail("Expected supported width and height") }
 let info = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String:Any]] ?? []
 let owned = info.filter { ($0[kCGWindowOwnerPID as String] as? Int32) == pid && ($0[kCGWindowLayer as String] as? Int) == 0 }
 guard owned.count == 1, let raw = owned[0][kCGWindowBounds as String] as? NSDictionary,
       let bounds = CGRect(dictionaryRepresentation: raw) else { fail("Expected one owned dashboard") }
 AXUIElementSetAttributeValue(app,kAXFrontmostAttribute as CFString,kCFBooleanTrue)
 let start = CGPoint(x: bounds.maxX - 2, y: bounds.maxY - 2)
 let end = CGPoint(x: bounds.minX + width - 2, y: bounds.minY + height - 2)
 for (type, point) in [(CGEventType.mouseMoved, start), (.leftMouseDown, start), (.leftMouseDragged, end), (.leftMouseUp, end)] {
  guard let event = CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: point, mouseButton: .left) else { fail("Cannot create resize event") }
  event.post(tap: .cghidEventTap)
  Thread.sleep(forTimeInterval: 0.1)
 }
} else if mode == "search" {
 guard args.count == 4, args[3].utf16.count <= 200 else { fail("Expected bounded search text") }
 let matches = rows.filter { ($0["AXRole"] as? String) == "AXTextField" && ($0["AXTitle"] as? String) == "Search name, PID, or user…" }
 guard matches.count == 1, let index = matches[0]["index"] as? Int,
       AXUIElementSetAttributeValue(nodes[index], kAXFocusedAttribute as CFString, kCFBooleanTrue) == .success else { fail("Cannot focus process search") }
 guard let bounds = matches[0]["bounds"] as? [CGFloat], bounds.count == 4 else { fail("Missing search bounds") }
 let point = CGPoint(x: bounds[0] + bounds[2] / 2, y: bounds[1] + bounds[3] / 2)
 for type in [CGEventType.mouseMoved, .leftMouseDown, .leftMouseUp] {
  guard let event = CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: point, mouseButton: .left) else { fail("Cannot click process search") }
  event.post(tap: .cghidEventTap)
 }
 Thread.sleep(forTimeInterval: 0.1)
 for (code, flags) in [(CGKeyCode(0), CGEventFlags.maskCommand), (CGKeyCode(51), CGEventFlags())] {
  for down in [true, false] {
   guard let event = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: down) else { fail("Cannot create search key") }
   event.flags = flags
   event.postToPid(pid)
  }
 }
 if !args[3].isEmpty {
  let characters = Array(args[3].utf16)
  for down in [true, false] {
   guard let event = CGEvent(keyboardEventSource: nil, virtualKey: 0, keyDown: down) else { fail("Cannot create search text event") }
   event.keyboardSetUnicodeString(stringLength: characters.count, unicodeString: characters)
   event.postToPid(pid)
  }
 }
} else if mode == "key" {
 guard args.count == 4, let code = ["left": CGKeyCode(123), "right": CGKeyCode(124), "home": CGKeyCode(115), "end": CGKeyCode(119)][args[3]] else { fail("Expected a supported navigation key") }
 for down in [true, false] {
  guard let event = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: down) else { fail("Cannot create key event") }
  event.postToPid(pid)
 }
} else if mode == "focus-id" {
 guard args.count == 4 else { fail("Selector value required") }
 let matches = rows.filter { ($0["AXIdentifier"] as? String) == args[3] }
 guard matches.count == 1, let index = matches[0]["index"] as? Int,
       AXUIElementSetAttributeValue(nodes[index], kAXFocusedAttribute as CFString, kCFBooleanTrue) == .success else { fail("Cannot focus unique selector") }
} else if mode == "activate" {
 result["action_return"] = AXUIElementSetAttributeValue(app,kAXFrontmostAttribute as CFString,kCFBooleanTrue).rawValue
} else if mode != "snapshot" { fail("Unknown action") }
let data = try JSONSerialization.data(withJSONObject:result,options:[.sortedKeys])
print(String(data:data,encoding:.utf8)!)
