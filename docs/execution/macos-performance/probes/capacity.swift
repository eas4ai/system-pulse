import Foundation
import Darwin
func cpu() -> Double { var r = rusage(); getrusage(RUSAGE_SELF, &r); return Double(r.ru_utime.tv_sec+r.ru_stime.tv_sec)+Double(r.ru_utime.tv_usec+r.ru_stime.tv_usec)/1e6 }
let keys:Set<URLResourceKey> = [.volumeTotalCapacityKey,.volumeAvailableCapacityKey,.volumeAvailableCapacityForImportantUsageKey]
func bench(_ name:String,_ work:() throws -> Void) rethrows {var used=0.0;for _ in 0..<10 {let c=cpu();try work();used += cpu()-c;Thread.sleep(forTimeInterval:1)};print("\(name): cpu_seconds=\(used)")}
let paths=["/","/System/Volumes/Data"]
try bench("fresh_url") {for p in paths {let v=try URL(fileURLWithPath:p).resourceValues(forKeys:keys);precondition(v.volumeTotalCapacity != nil)}}
var urls=paths.map{URL(fileURLWithPath:$0)}
try bench("clear_capacity_keys") {for i in urls.indices {for key in keys {urls[i].removeCachedResourceValue(forKey:key)};let v=try urls[i].resourceValues(forKeys:keys);precondition(v.volumeTotalCapacity != nil)}}
try bench("clear_all_keys") {for i in urls.indices {urls[i].removeAllCachedResourceValues();let v=try urls[i].resourceValues(forKeys:keys);precondition(v.volumeTotalCapacity != nil)}}
