// Native desktop observations/actions. AXWindows avoids the application's self
// child.
#import <ApplicationServices/ApplicationServices.h>
#import <Foundation/Foundation.h>
#include <time.h>
#include <unistd.h>

static uint64_t stamp(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return t.tv_sec * 1000000000ULL + t.tv_nsec;
}
static NSDictionary *clockAnchor(void) {
  uint64_t before = stamp();
  struct timespec t;
  clock_gettime(CLOCK_REALTIME, &t);
  uint64_t wall = t.tv_sec * 1000000000ULL + t.tv_nsec, after = stamp();
  return @{
    @"monotonic_before_ns" : @(before),
    @"monotonic_after_ns" : @(after),
    @"unix_ns" : @(wall)
  };
}
static id attribute(AXUIElementRef node, CFStringRef key) {
  CFTypeRef value = NULL;
  AXError code = AXUIElementCopyAttributeValue(node, key, &value);
  if (code != kAXErrorSuccess) {
    if (value)
      CFRelease(value);
    return nil;
  }
  return CFBridgingRelease(value);
}
static NSString *textAttribute(AXUIElementRef node, CFStringRef key) {
  id v = attribute(node, key);
  return [v isKindOfClass:NSString.class] ? v : @"";
}
static CGRect frame(AXUIElementRef node) {
  id p = attribute(node, kAXPositionAttribute),
     s = attribute(node, kAXSizeAttribute);
  CGPoint point;
  CGSize size;
  if (!p || !s || CFGetTypeID((__bridge CFTypeRef)p) != AXValueGetTypeID() ||
      CFGetTypeID((__bridge CFTypeRef)s) != AXValueGetTypeID() ||
      !AXValueGetValue((__bridge AXValueRef)p, kAXValueCGPointType, &point) ||
      !AXValueGetValue((__bridge AXValueRef)s, kAXValueCGSizeType, &size))
    return CGRectZero;
  return (CGRect){point, size};
}
static NSArray *rectangle(CGRect r) {
  return @[ @(r.origin.x), @(r.origin.y), @(r.size.width), @(r.size.height) ];
}
static CGRect clipped(CGRect a, CGRect b) {
  CGFloat x = MAX(CGRectGetMinX(a), CGRectGetMinX(b));
  CGFloat y = MAX(CGRectGetMinY(a), CGRectGetMinY(b));
  return CGRectMake(x, y, MAX(0, MIN(CGRectGetMaxX(a), CGRectGetMaxX(b)) - x),
                    MAX(0, MIN(CGRectGetMaxY(a), CGRectGetMaxY(b)) - y));
}
static void walk(AXUIElementRef node, CGRect clip, NSMutableArray *rows,
                 NSMutableArray *nodes, CFMutableSetRef visited,
                 NSUInteger depth, BOOL *complete, NSNumber *parent) {
  if (depth > 64 || rows.count >= 10000) {
    *complete = NO;
    return;
  }
  if (CFSetContainsValue(visited, node)) {
    *complete = NO;
    [rows addObject:@{
      @"cycle" : @YES,
      @"object_key" : [@(CFHash(node)) stringValue],
      @"parent_key" : parent ? parent.stringValue : [NSNull null]
    }];
    [nodes addObject:(__bridge id)node];
    return;
  }
  CFSetAddValue(visited, node);
  NSString *role = textAttribute(node, kAXRoleAttribute);
  CGRect bounds = frame(node);
  NSString *identifier = textAttribute(node, kAXIdentifierAttribute);
  NSString *title = textAttribute(node, kAXTitleAttribute),
           *description = textAttribute(node, kAXDescriptionAttribute);
  id value = attribute(node, kAXValueAttribute);
  [rows addObject:@{
    @"identifier" : identifier,
    @"role" : role,
    @"title" : title,
    @"description" : description,
    @"value" : ([value isKindOfClass:NSString.class] ||
                [value isKindOfClass:NSNumber.class])
        ? value
        : @"",
    @"frame" : rectangle(bounds),
    @"clip" : rectangle(clip),
    @"object_key" : [@(CFHash(node)) stringValue],
    @"parent_key" : parent ? parent.stringValue : [NSNull null]
  }];
  [nodes addObject:(__bridge id)node];
  NSString *monitor =
      NSProcessInfo.processInfo.environment[@"SYSTEM_PULSE_GPU_MONITOR_ID"];
  if (monitor.length && [identifier hasSuffix:@":viewport"] &&
      ![identifier isEqual:@"workspace:viewport"] &&
      ![identifier isEqual:[monitor stringByAppendingString:@":viewport"]]) {
    NSMutableDictionary *excluded = [rows.lastObject mutableCopy];
    excluded[@"children_excluded"] = @YES;
    rows[rows.count - 1] = excluded;
    return;
  }
  if (([role isEqual:@"AXScrollArea"] || [identifier hasSuffix:@":viewport"]) &&
      bounds.size.width > 0 && bounds.size.height > 0)
    clip = clipped(clip, bounds);
  id children = attribute(node, kAXChildrenAttribute);
  if (children && ![children isKindOfClass:NSArray.class]) {
    *complete = NO;
    return;
  }
  for (id child in children) {
    if (CFGetTypeID((__bridge CFTypeRef)child) != AXUIElementGetTypeID()) {
      *complete = NO;
      continue;
    }
    walk((__bridge AXUIElementRef)child, clip, rows, nodes, visited, depth + 1,
         complete, @(CFHash(node)));
  }
}
static BOOL inside(NSDictionary *row, NSString *ancestor, NSDictionary *byKey) {
  NSMutableSet *seen = [NSMutableSet set];
  while (row[@"parent_key"] != [NSNull null]) {
    NSString *key = row[@"parent_key"];
    if (!key || !byKey[key] || [seen containsObject:key])
      @throw [NSException exceptionWithName:@"AX ancestry"
                                     reason:@"Broken native ancestry"
                                   userInfo:nil];
    if ([key isEqual:ancestor])
      return YES;
    [seen addObject:key];
    row = byKey[key];
  }
  return NO;
}
static NSUInteger resolve(NSArray *rows, NSDictionary *selector) {
  NSMutableDictionary *byKey = [NSMutableDictionary dictionary];
  for (NSDictionary *row in rows) {
    if (!row[@"object_key"] || byKey[row[@"object_key"]])
      return NSNotFound;
    byKey[row[@"object_key"]] = row;
  }
  NSMutableArray *scope = [NSMutableArray array];
  if (selector[@"identifier"]) {
    if (selector.count != 1 || ![selector[@"identifier"] length])
      return NSNotFound;
    for (NSDictionary *row in rows)
      if ([row[@"identifier"] isEqual:selector[@"identifier"]])
        [scope addObject:row];
  } else {
    NSSet *allowed = [NSSet setWithArray:@[ @"within", @"label", @"after" ]];
    for (NSString *key in selector)
      if (![allowed containsObject:key])
        return NSNotFound;
    if (![selector[@"within"] length] || ![selector[@"label"] length])
      return NSNotFound;
    NSMutableArray *parents = [NSMutableArray array];
    for (NSDictionary *row in rows)
      if ([row[@"identifier"] isEqual:selector[@"within"]] ||
          [row[@"title"] isEqual:selector[@"within"]])
        [parents addObject:row];
    if (parents.count != 1)
      return NSNotFound;
    NSMutableArray *scoped = [NSMutableArray array];
    for (NSDictionary *row in rows)
      if (inside(row, parents[0][@"object_key"], byKey))
        [scoped addObject:row];
    if (selector[@"after"]) {
      NSMutableIndexSet *indices = [NSMutableIndexSet indexSet];
      for (NSUInteger i = 0; i < scoped.count; i++)
        if ([scoped[i][@"identifier"] isEqual:selector[@"after"]])
          [indices addIndex:i];
      if (indices.count != 1)
        return NSNotFound;
      NSUInteger start = indices.firstIndex + 1, end = scoped.count;
      NSString *prefix =
          [[[selector[@"after"] componentsSeparatedByString:@":value:"]
              firstObject] stringByAppendingString:@":value:"];
      for (NSUInteger i = start; i < scoped.count; i++)
        if ([scoped[i][@"identifier"] hasPrefix:prefix]) {
          end = i;
          break;
        }
      scoped = [[scoped subarrayWithRange:NSMakeRange(start, end - start)]
          mutableCopy];
    }
    for (NSDictionary *row in scoped)
      if ([row[@"title"] isEqual:selector[@"label"]] ||
          [row[@"description"] isEqual:selector[@"label"]] ||
          [row[@"value"] isEqual:selector[@"label"]])
        [scope addObject:row];
  }
  if (scope.count != 1)
    return NSNotFound;
  NSDictionary *row = scope[0];
  NSArray *f = row[@"frame"], *c = row[@"clip"];
  CGRect frameRect = CGRectMake([f[0] doubleValue], [f[1] doubleValue],
                                [f[2] doubleValue], [f[3] doubleValue]);
  CGRect clipRect = CGRectMake([c[0] doubleValue], [c[1] doubleValue],
                               [c[2] doubleValue], [c[3] doubleValue]);
  if (CGRectIsEmpty(frameRect) || CGRectIsEmpty(clipRect) ||
      !CGRectContainsRect(clipRect, frameRect))
    return NSNotFound;
  return [rows indexOfObjectIdenticalTo:row];
}
static NSDictionary *capture(AXUIElementRef app, NSMutableArray *nodes) {
  NSDictionary *clock = clockAnchor();
  CFTypeRef original = NULL;
  AXError windowsCode =
      AXUIElementCopyAttributeValue(app, kAXWindowsAttribute, &original);
  id windows = original ? CFBridgingRelease(original) : nil;
  NSMutableArray *rows = [NSMutableArray array];
  BOOL complete = YES;
  if (![windows isKindOfClass:NSArray.class] || [windows count] == 0 ||
      [windows count] > 32)
    complete = NO;
  else {
    CFMutableSetRef visited = CFSetCreateMutable(NULL, 0, &kCFTypeSetCallBacks);
    @try {
      for (id window in windows) {
        CGRect clip = frame((__bridge AXUIElementRef)window);
        walk((__bridge AXUIElementRef)window, clip, rows, nodes, visited, 0,
             &complete, nil);
      }
    } @finally {
      CFRelease(visited);
    }
  }
  id minimized = attribute(app, kAXMinimizedAttribute),
     frontmost = attribute(app, kAXFrontmostAttribute);
  pid_t target = 0;
  AXError pidCode = AXUIElementGetPid(app, &target);
  CFArrayRef attributes = NULL;
  AXError attributesCode = AXUIElementCopyAttributeNames(app, &attributes);
  id names = attributes ? CFBridgingRelease(attributes) : @[];
  return @{
    @"observed_ns" : @(stamp()),
    @"clock_anchor" : clock,
    @"complete" : @(complete),
    @"elements" : rows,
    @"windows_return" : @(windowsCode),
    @"windows_count" :
        ([windows isKindOfClass:NSArray.class] ? @([windows count]) : @0),
    @"windows_type" : windows ? NSStringFromClass([windows class]) : @"null",
    @"role" : textAttribute(app, kAXRoleAttribute),
    @"frontmost" : frontmost ?: [NSNull null],
    @"minimized" : minimized ?: [NSNull null],
    @"target_pid" : @(target),
    @"pid_return" : @(pidCode),
    @"observer_pid" : @(getpid()),
    @"observer_parent_pid" : @(getppid()),
    @"attribute_names_return" : @(attributesCode),
    @"attribute_names" : names,
    @"census_monitor" : NSProcessInfo.processInfo
            .environment[@"SYSTEM_PULSE_GPU_MONITOR_ID"]
        ?: @""
  };
}
static void output(id value) {
  NSError *e = nil;
  NSData *d = [NSJSONSerialization dataWithJSONObject:value
                                              options:NSJSONWritingSortedKeys
                                                error:&e];
  if (!d)
    @throw [NSException exceptionWithName:@"AX serialization"
                                   reason:e.description
                                 userInfo:nil];
  fwrite(d.bytes, 1, d.length, stdout);
  fputc('\n', stdout);
  fflush(stdout);
}

int gpuAX(int argc, const char **argv) {
  @autoreleasepool {
    if (argc < 1 || argc > 4 || !AXIsProcessTrusted()) {
      fprintf(
          stderr,
          "AX PID [TARGET press|scroll VALUE]; accessibility trust required\n");
      return 2;
    }
    pid_t pid = (pid_t)strtol(argv[0], NULL, 10);
    if (pid <= 0)
      return 2;
    AXUIElementRef app = AXUIElementCreateApplication(pid);
    AXUIElementSetMessagingTimeout(app, 2.0);
    @try {
      AXError enhanced = AXUIElementSetAttributeValue(
          app, CFSTR("AXEnhancedUserInterface"), kCFBooleanTrue);
      AXError manual = AXUIElementSetAttributeValue(
          app, CFSTR("AXManualAccessibility"), kCFBooleanTrue);
      AXError frontmost = AXUIElementSetAttributeValue(
          app, kAXFrontmostAttribute, kCFBooleanTrue);
      NSMutableArray *nodes = [NSMutableArray array];
      NSDictionary *before = capture(app, nodes);
      if (argc == 1) {
        NSMutableDictionary *result = [before mutableCopy];
        result[@"activation_returns"] = @{
          @"enhanced" : @(enhanced),
          @"manual" : @(manual),
          @"frontmost" : @(frontmost)
        };
        output(result);
        return 0;
      }
      if (argc == 2 && [@(argv[1]) isEqual:@"close"]) {
        id windows = attribute(app, kAXWindowsAttribute);
        if (![windows isKindOfClass:NSArray.class] || [windows count] != 1)
          return 3;
        id button = attribute((__bridge AXUIElementRef)windows[0],
                              kAXCloseButtonAttribute);
        if (!button ||
            CFGetTypeID((__bridge CFTypeRef)button) != AXUIElementGetTypeID())
          return 3;
        AXError code = AXUIElementPerformAction((__bridge AXUIElementRef)button,
                                                kAXPressAction);
        output(@{
          @"target_pid" : @(pid),
          @"method" : @"AXPressCloseButton",
          @"return_code" : @(code),
          @"before" : before
        });
        return code == kAXErrorSuccess ? 0 : 4;
      }
      if (argc < 3)
        return 2;
      NSError *requestError = nil;
      NSDictionary *request = [NSJSONSerialization
          JSONObjectWithData:[@(argv[1]) dataUsingEncoding:NSUTF8StringEncoding]
                     options:0
                       error:&requestError];
      if (![request isKindOfClass:NSDictionary.class] || requestError)
        return 2;
      NSString *target = request[@"control"], *method = @(argv[2]);
      NSDictionary *selector = request[@"selector"];
      if (![target isKindOfClass:NSString.class] ||
          ![selector isKindOfClass:NSDictionary.class])
        return 2;
      NSArray *rows = before[@"elements"];
      NSUInteger index = resolve(rows, selector);
      if (index == NSNotFound) {
        fprintf(stderr, "Native selector absent, ambiguous or invisible\n");
        output(before);
        return 3;
      }
      AXUIElementRef node = (__bridge AXUIElementRef)nodes[index];
      uint64_t start = stamp();
      AXError result = kAXErrorActionUnsupported;
      NSString *recorded = method;
      if ([method isEqual:@"press"]) {
        result = AXUIElementPerformAction(node, kAXPressAction);
        recorded = @"AXPress";
      } else if ([method isEqual:@"scroll"] && argc == 4) {
        int delta = atoi(argv[3]);
        if (delta < -100 || delta > 100 || delta == 0)
          return 2;
        CGRect r = frame(node);
        if (r.size.width <= 0 || r.size.height <= 0)
          return 3;
        CGEventRef event = CGEventCreateScrollWheelEvent(
            NULL, kCGScrollEventUnitLine, 1, delta);
        if (!event)
          return 3;
        CGEventSetLocation(event,
                           CGPointMake(CGRectGetMidX(r), CGRectGetMidY(r)));
        CGEventPost(kCGHIDEventTap, event);
        CFRelease(event);
        result = kAXErrorSuccess;
        recorded = @"CGEventScroll";
      } else if ([method isEqual:@"value"] && argc == 4) {
        result = AXUIElementSetAttributeValue(node, kAXValueAttribute,
                                              (__bridge CFTypeRef) @(argv[3]));
        recorded = @"AXSetValue";
      }
      usleep(250000);
      NSMutableArray *afterNodes = [NSMutableArray array];
      NSDictionary *after = capture(app, afterNodes);
      output(@{
        @"target" : target,
        @"selector" : selector,
        @"resolved_element" : rows[index],
        @"method" : recorded,
        @"return_code" : @(result),
        @"started_ns" : @(start),
        @"finished_ns" : @(stamp()),
        @"before" : before,
        @"after" : after
      });
      return result == kAXErrorSuccess ? 0 : 4;
    } @finally {
      CFRelease(app);
    }
  }
}
