import Foundation
import ApplicationServices
let args = CommandLine.arguments
func fail(_ message: String) -> Never { FileHandle.standardError.write(Data((message+"\n").utf8)); exit(1) }
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
} else if mode == "activate" {
 result["action_return"] = AXUIElementSetAttributeValue(app,kAXFrontmostAttribute as CFString,kCFBooleanTrue).rawValue
} else if mode != "snapshot" { fail("Unknown action") }
let data = try JSONSerialization.data(withJSONObject:result,options:[.sortedKeys])
print(String(data:data,encoding:.utf8)!)
