// Acceptance-only physical Intel workload. Requires Vulkan 1.1 and PCI
// identity.
#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <vulkan/vulkan.h>

enum { MAX_DEVICES = 32, MAX_EXTENSIONS = 512, MAX_QUEUES = 64 };
static const uint64_t BUFFER_BYTES = 4 * 1024 * 1024;
static const uint64_t FENCE_TIMEOUT_NS = 500000000;

static void need(bool valid, const char *stage) {
  if (!valid) {
    fprintf(stderr, "Intel Vulkan validation prerequisite/work failure: %s\n",
            stage);
    exit(3);
  }
}

static void checked(VkResult result, const char *stage) {
  if (result != VK_SUCCESS) {
    fprintf(stderr, "Intel Vulkan %s failed: VkResult=%d\n", stage, result);
    exit(3);
  }
}

static uint64_t stamp(clockid_t clock) {
  struct timespec value;
  need(clock_gettime(clock, &value) == 0, "clock_gettime");
  return (uint64_t)value.tv_sec * 1000000000 + (uint64_t)value.tv_nsec;
}

static bool pci_extension(VkPhysicalDevice device) {
  uint32_t count = 0;
  checked(vkEnumerateDeviceExtensionProperties(device, NULL, &count, NULL),
          "extension count");
  need(count <= MAX_EXTENSIONS, "extension enumeration bound");
  VkExtensionProperties extensions[MAX_EXTENSIONS];
  uint32_t capacity = count;
  checked(
      vkEnumerateDeviceExtensionProperties(device, NULL, &count, extensions),
      "extension enumeration");
  need(count == capacity, "extension enumeration changed");
  for (uint32_t i = 0; i < count; ++i)
    if (strcmp(extensions[i].extensionName,
               VK_EXT_PCI_BUS_INFO_EXTENSION_NAME) == 0)
      return true;
  return false;
}

int main(int argc, char **argv) {
  unsigned domain, bus, slot, function, seconds;
  int end = 0;
  need(argc == 3,
       "usage: gpu_intel_workload DOMAIN:BUS:DEVICE.FUNCTION SECONDS");
  need(sscanf(argv[1], "%x:%x:%x.%x%n", &domain, &bus, &slot, &function,
              &end) == 4 &&
           argv[1][end] == '\0' && domain <= 65535 && bus <= 255 &&
           slot <= 31 && function <= 7,
       "invalid PCI identity");
  end = 0;
  need(sscanf(argv[2], "%u%n", &seconds, &end) == 1 && argv[2][end] == '\0' &&
           seconds >= 1 && seconds <= 12,
       "duration must be 1 through 12 seconds");
  uint64_t anchor_before = stamp(CLOCK_MONOTONIC);
  uint64_t anchor_unix = stamp(CLOCK_REALTIME);
  uint64_t anchor_after = stamp(CLOCK_MONOTONIC);
  uint64_t query_started = stamp(CLOCK_MONOTONIC);
  VkApplicationInfo application = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
                                   .pApplicationName =
                                       "system-pulse-gpu-acceptance",
                                   .apiVersion = VK_API_VERSION_1_1};
  VkInstanceCreateInfo instance_info = {
      .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
      .pApplicationInfo = &application};
  VkInstance instance;
  checked(vkCreateInstance(&instance_info, NULL, &instance),
          "Vulkan 1.1 instance/loader");
  uint32_t count = 0;
  checked(vkEnumeratePhysicalDevices(instance, &count, NULL),
          "physical device count");
  need(count > 0 && count <= MAX_DEVICES, "physical device enumeration bound");
  VkPhysicalDevice devices[MAX_DEVICES];
  uint32_t capacity = count;
  checked(vkEnumeratePhysicalDevices(instance, &count, devices),
          "physical device enumeration");
  need(count == capacity, "physical device enumeration changed");
  VkPhysicalDevicePCIBusInfoPropertiesEXT identities[MAX_DEVICES] = {0};
  VkPhysicalDeviceProperties2 properties[MAX_DEVICES] = {0};
  bool has_pci[MAX_DEVICES] = {0};
  uint32_t selected_index = 0, matches = 0;
  for (uint32_t i = 0; i < count; ++i) {
    has_pci[i] = pci_extension(devices[i]);
    identities[i].sType =
        VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PCI_BUS_INFO_PROPERTIES_EXT;
    properties[i].sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2;
    properties[i].pNext = has_pci[i] ? &identities[i] : NULL;
    vkGetPhysicalDeviceProperties2(devices[i], &properties[i]);
    if (has_pci[i] && identities[i].pciDomain == domain &&
        identities[i].pciBus == bus && identities[i].pciDevice == slot &&
        identities[i].pciFunction == function) {
      selected_index = i;
      ++matches;
    }
  }
  need(matches == 1, "selected PCI device absent/ambiguous or "
                     "VK_EXT_pci_bus_info unavailable");
  VkPhysicalDevice selected = devices[selected_index];
  VkPhysicalDeviceProperties props = properties[selected_index].properties;
  need(props.vendorID == 0x8086 && props.apiVersion >= VK_API_VERSION_1_1,
       "selected device is not Intel Vulkan 1.1 hardware");
  uint64_t query_finished = stamp(CLOCK_MONOTONIC);
  uint32_t queue_count = 0;
  vkGetPhysicalDeviceQueueFamilyProperties(selected, &queue_count, NULL);
  need(queue_count > 0 && queue_count <= MAX_QUEUES, "queue enumeration bound");
  VkQueueFamilyProperties queues[MAX_QUEUES];
  capacity = queue_count;
  vkGetPhysicalDeviceQueueFamilyProperties(selected, &queue_count, queues);
  need(capacity == queue_count, "queue enumeration changed");
  uint32_t family = queue_count;
  for (uint32_t i = 0; i < queue_count; ++i)
    if (queues[i].queueCount &&
        (queues[i].queueFlags & (VK_QUEUE_TRANSFER_BIT | VK_QUEUE_COMPUTE_BIT |
                                 VK_QUEUE_GRAPHICS_BIT))) {
      family = i;
      break;
    }
  need(family < queue_count, "no transfer-capable queue");
  float priority = 1.0f;
  VkDeviceQueueCreateInfo queue_info = {
      .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
      .queueFamilyIndex = family,
      .queueCount = 1,
      .pQueuePriorities = &priority};
  VkDeviceCreateInfo device_info = {.sType =
                                        VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
                                    .queueCreateInfoCount = 1,
                                    .pQueueCreateInfos = &queue_info};
  VkDevice device;
  checked(vkCreateDevice(selected, &device_info, NULL, &device),
          "logical device");
  VkQueue queue;
  vkGetDeviceQueue(device, family, 0, &queue);
  VkBufferCreateInfo buffer_info = {.sType =
                                        VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
                                    .size = BUFFER_BYTES,
                                    .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                                    .sharingMode = VK_SHARING_MODE_EXCLUSIVE};
  VkBuffer buffer;
  checked(vkCreateBuffer(device, &buffer_info, NULL, &buffer), "4 MiB buffer");
  VkMemoryRequirements memory_requirements;
  vkGetBufferMemoryRequirements(device, buffer, &memory_requirements);
  need(memory_requirements.size >= BUFFER_BYTES &&
           memory_requirements.size <= 64 * 1024 * 1024,
       "device allocation exceeds bound");
  VkPhysicalDeviceMemoryProperties memory_properties;
  vkGetPhysicalDeviceMemoryProperties(selected, &memory_properties);
  need(memory_properties.memoryTypeCount <= VK_MAX_MEMORY_TYPES,
       "memory type enumeration bound");
  uint32_t memory_type = memory_properties.memoryTypeCount;
  for (uint32_t i = 0; i < memory_properties.memoryTypeCount; ++i)
    if ((memory_requirements.memoryTypeBits & (1u << i)) &&
        (memory_properties.memoryTypes[i].propertyFlags &
         VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)) {
      memory_type = i;
      break;
    }
  need(memory_type < memory_properties.memoryTypeCount,
       "no compatible device-local allocation");
  VkMemoryAllocateInfo allocation = {.sType =
                                         VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
                                     .allocationSize = memory_requirements.size,
                                     .memoryTypeIndex = memory_type};
  VkDeviceMemory memory;
  checked(vkAllocateMemory(device, &allocation, NULL, &memory),
          "bounded device memory");
  checked(vkBindBufferMemory(device, buffer, memory, 0),
          "buffer memory binding");
  VkCommandPoolCreateInfo pool_info = {
      .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
      .queueFamilyIndex = family};
  VkCommandPool pool;
  checked(vkCreateCommandPool(device, &pool_info, NULL, &pool), "command pool");
  VkCommandBufferAllocateInfo command_info = {
      .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
      .commandPool = pool,
      .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
      .commandBufferCount = 1};
  VkCommandBuffer command;
  checked(vkAllocateCommandBuffers(device, &command_info, &command),
          "one command buffer");
  VkCommandBufferBeginInfo begin = {
      .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
  checked(vkBeginCommandBuffer(command, &begin), "command begin");
  VkBufferMemoryBarrier barrier = {
      .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
      .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
      .dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
      .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
      .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
      .buffer = buffer,
      .size = BUFFER_BYTES};
  vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT,
                       VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 1, &barrier,
                       0, NULL);
  vkCmdFillBuffer(command, buffer, 0, BUFFER_BYTES, 0xa5a5a5a5);
  checked(vkEndCommandBuffer(command), "command end");
  VkFenceCreateInfo fence_info = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
  VkFence fence;
  checked(vkCreateFence(device, &fence_info, NULL, &fence), "one fence");
  VkSubmitInfo submit = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
                         .commandBufferCount = 1,
                         .pCommandBuffers = &command};
  uint64_t work_started = stamp(CLOCK_MONOTONIC), work_finished = work_started;
  uint64_t stop = work_started + (uint64_t)seconds * 1000000000;
  uint64_t completed = 0;
  while (stamp(CLOCK_MONOTONIC) + FENCE_TIMEOUT_NS < stop) {
    need(completed < 2000000, "submission count bound");
    checked(vkQueueSubmit(queue, 1, &submit, fence),
            "serial buffer-fill submit");
    checked(vkWaitForFences(device, 1, &fence, VK_TRUE, FENCE_TIMEOUT_NS),
            "completed submission fence");
    work_finished = stamp(CLOCK_MONOTONIC);
    ++completed;
    checked(vkResetFences(device, 1, &fence), "fence reset after completion");
  }
  need(completed > 0 && work_finished <= stop, "no bounded completed GPU work");
  vkDestroyFence(device, fence, NULL);
  vkDestroyCommandPool(device, pool, NULL);
  vkDestroyBuffer(device, buffer, NULL);
  vkFreeMemory(device, memory, NULL);
  vkDestroyDevice(device, NULL);
  vkDestroyInstance(instance, NULL);
  printf("{\"schema\":1,\"api\":\"Vulkan\",\"pid\":%d,\"pci\":\"%04x:%02x:%02x."
         "%x\","
         "\"vendor_id\":%u,\"device_id\":%u,\"identity_extension\":true,"
         "\"matching_devices\":%u,"
         "\"clock_anchor\":{\"monotonic_before_ns\":%" PRIu64
         ",\"monotonic_after_ns\":%" PRIu64 ",\"unix_ns\":%" PRIu64 "},"
         "\"query_started_ns\":%" PRIu64 ",\"query_finished_ns\":%" PRIu64
         ",\"work_started_ns\":%" PRIu64 ",\"work_finished_ns\":%" PRIu64 ","
         "\"duration_ns\":%" PRIu64 ",\"bytes\":%" PRIu64
         ",\"allocation_bytes\":%" PRIu64 ","
         "\"commands_submitted\":%" PRIu64 ",\"commands_completed\":%" PRIu64
         ",\"max_in_flight\":1,"
         "\"queue_family\":%u,\"queue_flags\":%u,\"fence_timeout_ns\":%" PRIu64
         ",\"devices\":[",
         getpid(), domain, bus, slot, function, props.vendorID, props.deviceID,
         matches, anchor_before, anchor_after, anchor_unix, query_started,
         query_finished, work_started, work_finished,
         work_finished - work_started, BUFFER_BYTES,
         (uint64_t)memory_requirements.size, completed, completed, family,
         queues[family].queueFlags, FENCE_TIMEOUT_NS);
  for (uint32_t i = 0; i < count; ++i) {
    printf("%s{\"vendor_id\":%u,\"device_id\":%u,\"identity_extension\":%s",
           i ? "," : "", properties[i].properties.vendorID,
           properties[i].properties.deviceID, has_pci[i] ? "true" : "false");
    if (has_pci[i])
      printf(",\"pci\":\"%04x:%02x:%02x.%x\"", identities[i].pciDomain,
             identities[i].pciBus, identities[i].pciDevice,
             identities[i].pciFunction);
    printf("}");
  }
  printf("]}\n");
  return 0;
}
