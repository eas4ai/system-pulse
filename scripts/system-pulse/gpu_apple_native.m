// Independent native operands and a bounded serial Metal workload.
// Build: clang -fobjc-arc -framework Foundation -framework Metal -framework
// IOKit
//        -framework ApplicationServices gpu_apple_native.m gpu_apple_ax.m -o
//        gpu-apple-native
#import <ApplicationServices/ApplicationServices.h>
#import <Foundation/Foundation.h>
#import <IOKit/IOKitLib.h>
#import <Metal/Metal.h>
#include <dlfcn.h>
#include <time.h>
#include <unistd.h>

static void need(BOOL condition, NSString *message) {
  if (!condition)
    @throw [NSException exceptionWithName:@"GPU evidence"
                                   reason:message
                                 userInfo:nil];
}
static uint64_t now(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return t.tv_sec * 1000000000ULL + t.tv_nsec;
}
static NSDictionary *anchor(void) {
  uint64_t a = now();
  struct timespec t;
  clock_gettime(CLOCK_REALTIME, &t);
  uint64_t b = now();
  return @{
    @"monotonic_before_ns" : @(a),
    @"monotonic_after_ns" : @(b),
    @"unix_ns" : @(t.tv_sec * 1000000000ULL + t.tv_nsec)
  };
}
static void emit(id record) {
  NSError *error = nil;
  NSData *data = [NSJSONSerialization dataWithJSONObject:record
                                                 options:NSJSONWritingSortedKeys
                                                   error:&error];
  need(data != nil, error.description);
  fwrite(data.bytes, 1, data.length, stdout);
  fputc('\n', stdout);
  fflush(stdout);
}
static NSDictionary *properties(io_registry_entry_t entry) {
  CFMutableDictionaryRef dictionary = NULL;
  kern_return_t code = IORegistryEntryCreateCFProperties(
      entry, &dictionary, kCFAllocatorDefault, 0);
  need(code == KERN_SUCCESS && dictionary != NULL,
       [NSString stringWithFormat:@"IOKit properties return %d", code]);
  return CFBridgingRelease(dictionary);
}
static NSArray *inventory(void) {
  NSArray<id<MTLDevice>> *devices = MTLCopyAllDevices();
  need(devices.count > 0 && devices.count <= 16,
       @"No bounded Metal device inventory");
  NSMutableArray *result = [NSMutableArray array];
  for (id<MTLDevice> device in devices) {
    io_registry_entry_t entry = IOServiceGetMatchingService(
        kIOMainPortDefault, IORegistryEntryIDMatching(device.registryID));
    need(entry != 0, @"Metal registry identity missing");
    NSMutableArray *ancestry = [NSMutableArray array];
    NSString *physical = nil;
    @try {
      for (NSUInteger n = 0; n < 32; n++) {
        io_string_t path;
        kern_return_t code =
            IORegistryEntryGetPath(entry, kIODeviceTreePlane, path);
        if (code == KERN_SUCCESS) {
          physical = @(path);
          break;
        }
        code = IORegistryEntryGetPath(entry, kIOServicePlane, path);
        if (code == KERN_SUCCESS)
          [ancestry addObject:@(path)];
        io_registry_entry_t parent = 0;
        need(IORegistryEntryGetParentEntry(entry, kIOServicePlane, &parent) ==
                 KERN_SUCCESS,
             @"No physical GPU parent");
        IOObjectRelease(entry);
        entry = parent;
      }
      need(physical != nil && [physical containsString:@"/sgx@"],
           @"No physical Apple GPU path");
      [result addObject:@{
        @"name" : device.name,
        @"registry_id" : @(device.registryID),
        @"physical_path" : physical,
        @"has_unified_memory" : @(device.hasUnifiedMemory),
        @"ancestry" : ancestry
      }];
    } @finally {
      IOObjectRelease(entry);
    }
  }
  return result;
}

typedef CFDictionaryRef (*CopyAll)(uint64_t, uint64_t);
typedef CFTypeRef (*Subscribe)(void *, CFDictionaryRef, CFDictionaryRef *,
                               uint64_t, CFTypeRef);
typedef CFDictionaryRef (*Sample)(CFTypeRef, CFDictionaryRef, CFTypeRef);
typedef CFStringRef (*StringGetter)(CFDictionaryRef);
typedef uint64_t (*NumberGetter)(CFDictionaryRef);
typedef uint8_t (*FormatGetter)(CFDictionaryRef);
typedef int (*StateCount)(CFDictionaryRef);
typedef CFStringRef (*StateName)(CFDictionaryRef, int);
typedef int64_t (*IntegerGetter)(CFDictionaryRef, int);

static void *symbol(void *library, const char *name) {
  void *p = dlsym(library, name);
  need(p != NULL, [NSString stringWithFormat:@"Missing native API %s", name]);
  return p;
}
static NSString *stringValue(CFStringRef value) {
  need(value && CFGetTypeID(value) == CFStringGetTypeID(),
       @"Missing IOReport string");
  return (__bridge NSString *)value;
}

static NSDictionary *channel(CFDictionaryRef item, void *library, BOOL values) {
  NSMutableDictionary *row = [NSMutableDictionary dictionary];
  NSDictionary *strings = @{
    @"group" : @"IOReportChannelGetGroup",
    @"subgroup" : @"IOReportChannelGetSubGroup",
    @"channel" : @"IOReportChannelGetChannelName",
    @"unit" : @"IOReportChannelGetUnitLabel"
  };
  for (NSString *key in strings) {
    CFStringRef value =
        ((StringGetter)symbol(library, [strings[key] UTF8String]))(item);
    row[key] = value ? stringValue(value) : @"";
  }
  row[@"format"] =
      @(((FormatGetter)symbol(library, "IOReportChannelGetFormat"))(item));
  NSDictionary *numbers = @{
    @"driver_id" : @"IOReportChannelGetDriverID",
    @"channel_id" : @"IOReportChannelGetChannelID",
    @"encoded_unit" : @"IOReportChannelGetUnit"
  };
  for (NSString *key in numbers)
    row[key] =
        @(((NumberGetter)symbol(library, [numbers[key] UTF8String]))(item));
  if (values) {
    if ([row[@"format"] unsignedLongLongValue] == 2) {
      int count = ((StateCount)symbol(library, "IOReportStateGetCount"))(item);
      need(count > 0 && count <= 128, @"Invalid native state count");
      NSMutableArray *states = [NSMutableArray array];
      for (int n = 0; n < count; n++) {
        int64_t ticks =
            ((IntegerGetter)symbol(library, "IOReportStateGetResidency"))(item,
                                                                          n);
        need(ticks >= 0, @"Negative native residency");
        [states addObject:@{
          @"name" : stringValue(((StateName)symbol(
              library, "IOReportStateGetNameForIndex"))(item, n)),
          @"residency" : @(ticks)
        }];
      }
      row[@"states"] = states;
    } else if ([row[@"format"] unsignedLongLongValue] == 1) {
      row[@"integer"] = @(((IntegerGetter)symbol(
          library, "IOReportSimpleGetIntegerValue"))(item, 0));
    }
  }
  return row;
}

static NSArray *memory(NSArray *devices) {
  NSMutableArray *rows = [NSMutableArray array];
  for (NSDictionary *device in devices) {
    uint64_t start = now();
    io_registry_entry_t entry = IOServiceGetMatchingService(
        kIOMainPortDefault, IORegistryEntryIDMatching([device[@"registry_id"]
                                unsignedLongLongValue]));
    need(entry != 0, @"Accelerator disappeared");
    @try {
      NSDictionary *p = properties(entry);
      uint64_t end = now();
      NSDictionary *stats = p[@"PerformanceStatistics"];
      need(!stats || [stats isKindOfClass:NSDictionary.class],
           @"Invalid accelerator statistics");
      NSMutableDictionary *values = [NSMutableDictionary dictionary];
      for (NSString *key in
           @[ @"Alloc system memory", @"In use system memory" ]) {
        id value = stats[key];
        if (value) {
          need([value isKindOfClass:NSNumber.class], @"Invalid memory counter");
          values[key] = value;
        }
      }
      [rows addObject:@{
        @"start" : @(start),
        @"end" : @(end),
        @"registry_id" : device[@"registry_id"],
        @"values" : values
      }];
    } @finally {
      IOObjectRelease(entry);
    }
  }
  return rows;
}
static NSArray *tables(void) {
  io_iterator_t iterator = 0;
  need(IOServiceGetMatchingServices(kIOMainPortDefault,
                                    IOServiceNameMatching("pmgr"),
                                    &iterator) == KERN_SUCCESS,
       @"pmgr inventory failed");
  NSMutableArray *rows = [NSMutableArray array];
  io_registry_entry_t entry = 0;
  @try {
    while ((entry = IOIteratorNext(iterator))) {
      @try {
        need(rows.count < 16, @"pmgr inventory bound exceeded");
        uint64_t start = now();
        NSDictionary *p = properties(entry);
        uint64_t end = now();
        NSData *data = p[@"voltage-states9"];
        if (data) {
          need([data isKindOfClass:NSData.class] && data.length <= 1024 &&
                   data.length % 8 == 0,
               @"Invalid voltage table");
          NSMutableString *hex = [NSMutableString string];
          const uint8_t *bytes = data.bytes;
          for (NSUInteger n = 0; n < data.length; n++)
            [hex appendFormat:@"%02x", bytes[n]];
          uint64_t identity = 0;
          need(IORegistryEntryGetRegistryEntryID(entry, &identity) ==
                   KERN_SUCCESS,
               @"pmgr identity failed");
          io_string_t physical;
          need(IORegistryEntryGetPath(entry, kIODeviceTreePlane, physical) ==
                   KERN_SUCCESS,
               @"pmgr physical path failed");
          [rows addObject:@{
            @"start" : @(start),
            @"end" : @(end),
            @"registry_id" : @(identity),
            @"physical_path" : @(physical),
            @"voltage_states9_hex" : hex
          }];
        }
      } @finally {
        IOObjectRelease(entry);
        entry = 0;
      }
    }
  } @finally {
    IOObjectRelease(iterator);
  }
  return rows;
}

// Native read-only AppleSMC struct method 2. Retain bytes and status before
// decoding.
typedef struct {
  uint32_t key;
  uint8_t version[6];
  uint8_t padding1[2];
  uint8_t limit[16];
  uint32_t size, type;
  uint8_t attributes;
  uint8_t padding2[3];
  uint8_t result, status, command, padding3;
  uint32_t data32;
  uint8_t bytes[32];
} SMCRequest;
_Static_assert(sizeof(SMCRequest) == 80, "SMC ABI");
static NSDictionary *smc(NSString *key) {
  uint64_t start = now();
  io_iterator_t iterator = 0;
  io_service_t service = 0, candidate = 0;
  NSUInteger count = 0, seen = 0;
  kern_return_t discovery = IOServiceGetMatchingServices(
      kIOMainPortDefault, IOServiceMatching("AppleSMC"), &iterator);
  if (discovery != KERN_SUCCESS)
    return @{
      @"key" : key,
      @"start" : @(start),
      @"end" : @(now()),
      @"return" : @(discovery),
      @"error" : @"SMC enumeration failed"
    };
  @try {
    while ((candidate = IOIteratorNext(iterator))) {
      io_name_t name;
      kern_return_t result = IORegistryEntryGetName(candidate, name);
      if (result == KERN_SUCCESS && strcmp(name, "AppleSMCKeysEndpoint") == 0) {
        count++;
        if (!service) {
          service = candidate;
          candidate = 0;
        }
      }
      if (candidate)
        IOObjectRelease(candidate);
      if (++seen > 1024) {
        if (service)
          IOObjectRelease(service);
        service = 0;
        need(NO, @"SMC enumeration bound exceeded");
      }
    }
  } @finally {
    IOObjectRelease(iterator);
  }
  if (count > 1) {
    if (service)
      IOObjectRelease(service);
    return @{
      @"key" : key,
      @"start" : @(start),
      @"end" : @(now()),
      @"error" : @"SMC endpoint ambiguous"
    };
  }
  if (!service)
    return @{
      @"key" : key,
      @"start" : @(start),
      @"end" : @(now()),
      @"error" : @"AppleSMC absent"
    };
  io_connect_t connection = 0;
  kern_return_t code = IOServiceOpen(service, mach_task_self(), 0, &connection);
  IOObjectRelease(service);
  if (code != KERN_SUCCESS)
    return @{
      @"key" : key,
      @"start" : @(start),
      @"end" : @(now()),
      @"return" : @(code),
      @"error" : @"AppleSMC open failed"
    };
  @try {
    const char *k = key.UTF8String;
    need(strlen(k) == 4, @"SMC key must be four bytes");
    SMCRequest input = {0}, output = {0};
    input.key = ((uint32_t)(uint8_t)k[0] << 24) |
                ((uint32_t)(uint8_t)k[1] << 16) |
                ((uint32_t)(uint8_t)k[2] << 8) | (uint8_t)k[3];
    input.command = 9;
    size_t size = sizeof(output);
    code = IOConnectCallStructMethod(connection, 2, &input, sizeof(input),
                                     &output, &size);
    if (code == KERN_SUCCESS && size == 80 && output.result == 0 &&
        output.status == 0 && output.size <= 32) {
      input.size = output.size;
      uint32_t type = output.type;
      input.command = 5;
      memset(&output, 0, sizeof(output));
      size = sizeof(output);
      code = IOConnectCallStructMethod(connection, 2, &input, sizeof(input),
                                       &output, &size);
      output.type = type;
      output.size = input.size;
    }
    NSMutableString *hex = [NSMutableString string];
    for (NSUInteger n = 0; n < MIN(output.size, 32); n++)
      [hex appendFormat:@"%02x", output.bytes[n]];
    return @{
      @"key" : key,
      @"start" : @(start),
      @"end" : @(now()),
      @"return" : @(code),
      @"output_size" : @(size),
      @"data_size" : @(output.size),
      @"data_type" : @(output.type),
      @"result" : @(output.result),
      @"status" : @(output.status),
      @"raw_hex" : hex
    };
  } @finally {
    IOServiceClose(connection);
  }
}

static NSDictionary *hid(void) {
  void *library = dlopen("/System/Library/Frameworks/IOKit.framework/IOKit",
                         RTLD_NOW | RTLD_LOCAL);
  if (!library)
    return @{@"error" : @"HID library unavailable"};
  CFTypeRef client = NULL;
  CFArrayRef services = NULL;
  @try {
    typedef CFTypeRef (*Create)(CFAllocatorRef);
    typedef void (*Matching)(CFTypeRef, CFDictionaryRef);
    typedef CFArrayRef (*Services)(CFTypeRef);
    typedef CFTypeRef (*Property)(CFTypeRef, CFStringRef);
    typedef CFTypeRef (*Event)(CFTypeRef, int64_t, int32_t, int64_t);
    typedef double (*FloatValue)(CFTypeRef, uint32_t);
    client = ((Create)symbol(library, "IOHIDEventSystemClientCreate"))(NULL);
    need(client != NULL, @"HID client absent");
    ((Matching)symbol(library, "IOHIDEventSystemClientSetMatching"))(
        client, (__bridge CFDictionaryRef)
                    @{@"PrimaryUsagePage" : @0xff00,
                      @"PrimaryUsage" : @5});
    services = ((Services)symbol(library,
                                 "IOHIDEventSystemClientCopyServices"))(client);
    need(services && CFGetTypeID(services) == CFArrayGetTypeID() &&
             CFArrayGetCount(services) <= 4096,
         @"HID service inventory invalid");
    NSMutableArray *products = [NSMutableArray array],
                   *rows = [NSMutableArray array];
    for (CFIndex n = 0; n < CFArrayGetCount(services); n++) {
      @autoreleasepool {
        CFTypeRef service = CFArrayGetValueAtIndex(services, n);
        CFTypeRef product =
            ((Property)symbol(library, "IOHIDServiceClientCopyProperty"))(
                service, CFSTR("Product"));
        if (!product) {
          [products addObject:[NSNull null]];
          continue;
        }
        NSString *name = nil;
        @try {
          need(CFGetTypeID(product) == CFStringGetTypeID(),
               @"Invalid HID product");
          name = [(__bridge NSString *)product copy];
        } @finally {
          CFRelease(product);
        }
        [products addObject:name];
        if (![name hasPrefix:@"GPU MTR Temp Sensor"])
          continue;
        NSString *suffix =
            [name substringFromIndex:[@"GPU MTR Temp Sensor" length]];
        if ([suffix rangeOfCharacterFromSet:[[NSCharacterSet
                                                decimalDigitCharacterSet]
                                                invertedSet]]
                .location != NSNotFound)
          continue;
        uint64_t start = now();
        CFTypeRef event =
            ((Event)symbol(library, "IOHIDServiceClientCopyEvent"))(service, 15,
                                                                    0, 0);
        uint64_t end = now();
        if (!event) {
          [rows addObject:@{
            @"product" : name,
            @"start" : @(start),
            @"end" : @(end),
            @"error" : @"HID temperature event absent"
          }];
          continue;
        }
        @try {
          double value = ((FloatValue)symbol(
              library, "IOHIDEventGetFloatValue"))(event, 15 << 16);
          need(isfinite(value), @"Nonfinite HID temperature");
          [rows addObject:@{
            @"product" : name,
            @"start" : @(start),
            @"end" : @(end),
            @"celsius" : @(value)
          }];
        } @finally {
          CFRelease(event);
        }
      }
    }
    return @{
      @"products" : products,
      @"rows" : rows,
      @"service_count" : @(CFArrayGetCount(services))
    };
  } @catch (NSException *error) {
    return @{@"error" : error.reason};
  } @finally {
    if (services)
      CFRelease(services);
    if (client)
      CFRelease(client);
    dlclose(library);
  }
}

static void observe(NSUInteger count, NSUInteger interval) {
  void *library = dlopen("/usr/lib/libIOReport.dylib", RTLD_NOW | RTLD_LOCAL);
  need(library != NULL, @"IOReport unavailable");
  CFDictionaryRef all = NULL, subscribed = NULL;
  CFTypeRef subscription = NULL;
  @try {
    NSArray *devices = inventory();
    all = ((CopyAll)symbol(library, "IOReportCopyAllChannels"))(0, 0);
    need(all != NULL, @"IOReport inventory absent");
    NSArray *channels = ((__bridge NSDictionary *)all)[@"IOReportChannels"];
    need([channels isKindOfClass:NSArray.class] && channels.count <= 100000,
         @"Invalid IOReport inventory");
    NSMutableArray *selected = [NSMutableArray array],
                   *metadata = [NSMutableArray array];
    for (NSDictionary *item in channels) {
      NSDictionary *row = channel((__bridge CFDictionaryRef)item, library, NO);
      if (([row[@"group"] isEqual:@"GPU Stats"] &&
           [row[@"subgroup"] isEqual:@"GPU Performance States"]) ||
          ([row[@"group"] isEqual:@"Energy Model"] &&
           [row[@"channel"] rangeOfString:@"GPU"
                                  options:NSCaseInsensitiveSearch]
                   .location != NSNotFound)) {
        [selected addObject:item];
        [metadata addObject:row];
      }
    }
    need(selected.count > 0 && selected.count <= 512,
         @"No bounded GPU channel selection");
    NSMutableDictionary *request = [(__bridge NSDictionary *)all mutableCopy];
    request[@"IOReportChannels"] = selected;
    subscription = ((Subscribe)symbol(library, "IOReportCreateSubscription"))(
        NULL, (__bridge CFDictionaryRef)request, &subscribed, 0, NULL);
    need(subscription != NULL && subscribed != NULL,
         @"IOReport subscription failed");
    for (NSUInteger index = 0; index < count; index++) {
      @autoreleasepool {
        NSDictionary *clock = anchor();
        uint64_t start = now();
        CFDictionaryRef sample = ((Sample)symbol(
            library, "IOReportCreateSamples"))(subscription, subscribed, NULL);
        uint64_t end = now();
        need(sample != NULL, @"IOReport read failed");
        NSMutableArray *values = [NSMutableArray array];
        @try {
          NSArray *rows =
              ((__bridge NSDictionary *)sample)[@"IOReportChannels"];
          need([rows isKindOfClass:NSArray.class] && rows.count <= 512,
               @"Invalid IOReport sample count");
          for (NSDictionary *item in rows)
            [values addObject:channel((__bridge CFDictionaryRef)item, library,
                                      YES)];
        } @finally {
          CFRelease(sample);
        }
        NSMutableArray *thermal = [NSMutableArray array];
        // Explicit M1 source profile. Other models must provide a reviewed
        // profile.
        if (devices.count == 1 && [devices[0][@"name"] hasPrefix:@"Apple M1"])
          for (NSString *key in @[ @"Tg05", @"Tg0D", @"Tg0L", @"Tg0T" ])
            [thermal addObject:smc(key)];
        emit(@{
          @"schema" : @1,
          @"pid" : @(getpid()),
          @"clock_anchor" : clock,
          @"devices" : inventory(),
          @"metadata" : metadata,
          @"ioreport" :
              @{@"start" : @(start), @"end" : @(end), @"channels" : values},
          @"memory" : memory(devices),
          @"tables" : tables(),
          @"smc" : thermal,
          @"hid" : hid()
        });
      }
      if (index + 1 < count)
        usleep((useconds_t)(interval * 1000));
    }
  } @finally {
    if (subscription)
      CFRelease(subscription);
    if (subscribed)
      CFRelease(subscribed);
    if (all)
      CFRelease(all);
    dlclose(library);
  }
}

static void workload(uint64_t registry, double seconds) {
  NSDictionary *workClock = anchor();
  uint64_t workStarted = 0, workFinished = 0;
  uint64_t start = now(), stop = start + (uint64_t)(seconds * 1e9);
  NSUInteger completed = 0;
  id<MTLDevice> selected = nil;
  for (id<MTLDevice> device in MTLCopyAllDevices())
    if (device.registryID == registry) {
      need(selected == nil, @"Duplicate Metal ID");
      selected = device;
    }
  need(selected != nil, @"Requested independent Metal device absent");
  NSError *error = nil;
  NSString *source = @"#include <metal_stdlib>\nusing namespace metal; kernel "
                     @"void work(device float *x [[buffer(0)]], uint i "
                     @"[[thread_position_in_grid]]) {float v=x[i]; for(uint "
                     @"n=0;n<256;n++) v=sin(v)+0.0001f; x[i]=v;}";
  id<MTLLibrary> library = [selected newLibraryWithSource:source
                                                  options:nil
                                                    error:&error];
  need(library != nil, error.description);
  id<MTLComputePipelineState> pipeline = [selected
      newComputePipelineStateWithFunction:[library newFunctionWithName:@"work"]
                                    error:&error];
  need(pipeline != nil, error.description);
  NSUInteger bytes = 4 * 1024 * 1024;
  id<MTLBuffer> buffer =
      [selected newBufferWithLength:bytes options:MTLResourceStorageModeShared];
  need(buffer != nil, @"Metal allocation failed");
  memset(buffer.contents, 0, bytes);
  id<MTLCommandQueue> queue = [selected newCommandQueue];
  need(queue != nil, @"Metal queue failed");
  while (now() + 100000000ULL < stop) {
    @autoreleasepool {
      id<MTLCommandBuffer> command = [queue commandBuffer];
      id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
      need(command && encoder, @"Metal command allocation failed");
      [encoder setComputePipelineState:pipeline];
      [encoder setBuffer:buffer offset:0 atIndex:0];
      [encoder dispatchThreads:MTLSizeMake(bytes / sizeof(float), 1, 1)
          threadsPerThreadgroup:MTLSizeMake(
                                    MIN(256,
                                        pipeline.maxTotalThreadsPerThreadgroup),
                                    1, 1)];
      [encoder endEncoding];
      if (!workStarted)
        workStarted = now();
      [command commit];
      [command waitUntilCompleted];
      need(command.status == MTLCommandBufferStatusCompleted,
           command.error.description);
      workFinished = now();
      completed++;
    }
  }
  emit(@{
    @"clock_anchor" : workClock,
    @"work_started_ns" : @(workStarted),
    @"work_finished_ns" : @(workFinished),
    @"registry_id" : @(registry),
    @"pid" : @(getpid()),
    @"bytes" : @(bytes),
    @"commands_completed" : @(completed),
    @"max_in_flight" : @1,
    @"duration_ns" : @(now() - start)
  });
}

extern int gpuAX(int argc, const char **argv);
int main(int argc, const char **argv) {
  @autoreleasepool {
    @try {
      need(argc >= 2, @"Expected inventory | observe COUNT INTERVAL_MS | "
                      @"workload REGISTRY_ID SECONDS | ax ...");
      NSString *mode = @(argv[1]);
      if ([mode isEqual:@"inventory"]) {
        emit(@{
          @"clock_anchor" : anchor(),
          @"devices" : inventory(),
          @"tables" : tables()
        });
      } else if ([mode isEqual:@"observe"]) {
        need(argc == 4, @"observe COUNT INTERVAL_MS");
        NSUInteger count = strtoul(argv[2], NULL, 10),
                   interval = strtoul(argv[3], NULL, 10);
        need(count >= 1 && count <= 100000 && interval >= 10 &&
                 interval <= 5000 && count * interval <= 3600000,
             @"Observation bounds");
        observe(count, interval);
      } else if ([mode isEqual:@"workload"]) {
        need(argc == 4, @"workload REGISTRY_ID SECONDS");
        double seconds = strtod(argv[3], NULL);
        need(seconds >= 1 && seconds <= 120, @"Workload duration bounds");
        workload(strtoull(argv[2], NULL, 10), seconds);
      } else if ([mode isEqual:@"ax"])
        return gpuAX(argc - 2, argv + 2);
      else
        need(NO, @"Unknown native helper mode");
      return 0;
    } @catch (NSException *error) {
      fprintf(stderr, "%s\n", error.reason.UTF8String);
      return 1;
    }
  }
}
