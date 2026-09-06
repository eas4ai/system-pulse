//! The native ABI boundary. All borrowed CF references are tied to an owner.
use super::super::{Outcome, bounded_count};
use std::{
    ffi::{CStr, CString, c_char, c_void},
    marker::PhantomData,
    ptr::{self, NonNull},
};
pub(super) type Ptr = *const c_void;
#[link(name = "CoreFoundation", kind = "framework")]
unsafe extern "C" {
    fn CFRelease(value: Ptr);
    fn CFRetain(value: Ptr) -> Ptr;
    fn CFGetTypeID(value: Ptr) -> usize;
    fn CFStringGetTypeID() -> usize;
    fn CFArrayGetTypeID() -> usize;
    fn CFDictionaryGetTypeID() -> usize;
    fn CFNumberGetTypeID() -> usize;
    fn CFDataGetTypeID() -> usize;
    fn CFStringGetLength(value: Ptr) -> isize;
    fn CFStringGetCString(value: Ptr, buffer: *mut c_char, size: isize, encoding: u32) -> u8;
    fn CFStringCreateWithCString(allocator: Ptr, text: *const c_char, encoding: u32) -> Ptr;
    fn CFArrayGetCount(value: Ptr) -> isize;
    fn CFArrayGetValueAtIndex(value: Ptr, index: isize) -> Ptr;
    fn CFArrayCreateMutable(allocator: Ptr, capacity: isize, callbacks: Ptr) -> Ptr;
    fn CFArrayAppendValue(array: Ptr, value: Ptr);
    fn CFDictionaryGetValue(dict: Ptr, key: Ptr) -> Ptr;
    fn CFDictionaryCreateMutableCopy(allocator: Ptr, capacity: isize, dict: Ptr) -> Ptr;
    fn CFDictionarySetValue(dict: Ptr, key: Ptr, value: Ptr);
    fn CFNumberGetValue(number: Ptr, kind: i32, value: *mut c_void) -> u8;
    fn CFNumberCreate(allocator: Ptr, kind: i32, value: Ptr) -> Ptr;
    fn CFDictionaryCreate(
        allocator: Ptr,
        keys: *const Ptr,
        values: *const Ptr,
        count: isize,
        key_callbacks: Ptr,
        value_callbacks: Ptr,
    ) -> Ptr;
    fn CFDataGetLength(data: Ptr) -> isize;
    fn CFDataGetBytePtr(data: Ptr) -> *const u8;
    static kCFTypeArrayCallBacks: u8;
    static kCFTypeDictionaryKeyCallBacks: u8;
    static kCFTypeDictionaryValueCallBacks: u8;
}
#[link(name = "IOKit", kind = "framework")]
unsafe extern "C" {
    fn IOObjectRelease(object: u32) -> i32;
    pub(super) fn IORegistryEntryIDMatching(identifier: u64) -> Ptr;
    pub(super) fn IOServiceGetMatchingService(port: u32, matching: Ptr) -> u32;
    pub(super) fn IOServiceMatching(name: *const c_char) -> Ptr;
    pub(super) fn IOServiceNameMatching(name: *const c_char) -> Ptr;
    pub(super) fn IOServiceGetMatchingServices(port: u32, matching: Ptr, iterator: *mut u32)
    -> i32;
    pub(super) fn IOIteratorNext(iterator: u32) -> u32;
    fn IORegistryEntryGetPath(entry: u32, plane: *const c_char, path: *mut c_char) -> i32;
    fn IORegistryEntryGetName(entry: u32, name: *mut c_char) -> i32;
    fn IORegistryEntryGetRegistryEntryID(entry: u32, id: *mut u64) -> i32;
    fn IORegistryEntryGetParentEntry(entry: u32, plane: *const c_char, parent: *mut u32) -> i32;
    fn IORegistryEntryCreateCFProperties(
        entry: u32,
        properties: *mut Ptr,
        allocator: Ptr,
        options: u32,
    ) -> i32;
    pub(super) fn IOServiceOpen(service: u32, task: u32, kind: u32, connection: *mut u32) -> i32;
    pub(super) fn IOServiceClose(connection: u32) -> i32;
    pub(super) fn IOConnectCallStructMethod(
        connection: u32,
        selector: u32,
        input: Ptr,
        input_size: usize,
        output: *mut c_void,
        output_size: *mut usize,
    ) -> i32;
}
#[link(name = "Metal", kind = "framework")]
unsafe extern "C" {
    pub(super) fn MTLCopyAllDevices() -> Ptr;
}
#[link(name = "objc")]
unsafe extern "C" {
    fn sel_registerName(name: *const c_char) -> Ptr;
    fn objc_msgSend();
}
unsafe extern "C" {
    pub(super) fn mach_task_self() -> u32;
}

pub(super) struct Cf(NonNull<c_void>);
#[derive(Clone, Copy)]
pub(super) struct Ref<'a> {
    ptr: Ptr,
    _owner: PhantomData<&'a Cf>,
}
impl Cf {
    /// The pointer must be null or an owned Create/Copy-rule CF object.
    pub(super) unsafe fn owned(ptr: Ptr) -> Outcome<Self> {
        NonNull::new(ptr.cast_mut())
            .map(Self)
            .ok_or("Native Create/Copy returned null".into())
    }
    pub(super) fn borrow(&self) -> Ref<'_> {
        Ref {
            ptr: self.0.as_ptr(),
            _owner: PhantomData,
        }
    }
    pub(super) fn ptr(&self) -> Ptr {
        self.0.as_ptr()
    }
    pub(super) fn string(value: &str) -> Outcome<Self> {
        let value = CString::new(value).map_err(|_| "NUL in CF string")?;
        // SAFETY: NUL-terminated input and the returned object follows Create ownership.
        unsafe {
            Self::owned(CFStringCreateWithCString(
                ptr::null(),
                value.as_ptr(),
                0x08000100,
            ))
        }
    }
    pub(super) fn array() -> Outcome<Self> {
        // SAFETY: standard retaining CF callbacks and Create ownership.
        unsafe {
            Self::owned(CFArrayCreateMutable(
                ptr::null(),
                0,
                ptr::addr_of!(kCFTypeArrayCallBacks).cast(),
            ))
        }
    }
    pub(super) fn append(&self, value: Ref<'_>) {
        unsafe { CFArrayAppendValue(self.ptr(), value.ptr) }
    }
    pub(super) fn dictionary_copy(value: Ref<'_>) -> Outcome<Self> {
        value.dictionary()?;
        unsafe { Self::owned(CFDictionaryCreateMutableCopy(ptr::null(), 0, value.ptr)) }
    }
    pub(super) fn set(&self, key: &Cf, value: &Cf) {
        unsafe { CFDictionarySetValue(self.ptr(), key.ptr(), value.ptr()) }
    }
    pub(super) fn hid_matching() -> Outcome<Self> {
        let keys = [
            Self::string("PrimaryUsagePage")?,
            Self::string("PrimaryUsage")?,
        ];
        let values = [0xff00i32, 5i32];
        let a = unsafe {
            Self::owned(CFNumberCreate(
                ptr::null(),
                3,
                ptr::addr_of!(values[0]).cast(),
            ))?
        };
        let b = unsafe {
            Self::owned(CFNumberCreate(
                ptr::null(),
                3,
                ptr::addr_of!(values[1]).cast(),
            ))?
        };
        let key_ptrs = [keys[0].ptr(), keys[1].ptr()];
        let val_ptrs = [a.ptr(), b.ptr()];
        unsafe {
            Self::owned(CFDictionaryCreate(
                ptr::null(),
                key_ptrs.as_ptr(),
                val_ptrs.as_ptr(),
                2,
                ptr::addr_of!(kCFTypeDictionaryKeyCallBacks).cast(),
                ptr::addr_of!(kCFTypeDictionaryValueCallBacks).cast(),
            ))
        }
    }
}
impl Drop for Cf {
    fn drop(&mut self) {
        unsafe { CFRelease(self.ptr()) }
    }
}
impl<'a> Ref<'a> {
    pub(super) fn ptr(self) -> Ptr {
        self.ptr
    }
    /// Pointer must be borrowed from this object's native lifetime.
    pub(super) unsafe fn child(self, ptr: Ptr) -> Outcome<Self> {
        if ptr.is_null() {
            Err("Native borrowed value absent".into())
        } else {
            Ok(Self {
                ptr,
                _owner: PhantomData,
            })
        }
    }
    fn expect(self, kind: usize) -> Outcome<()> {
        if unsafe { CFGetTypeID(self.ptr) } == kind {
            Ok(())
        } else {
            Err("Unexpected Core Foundation type".into())
        }
    }
    pub(super) fn dictionary(self) -> Outcome<()> {
        self.expect(unsafe { CFDictionaryGetTypeID() })
    }
    pub(super) fn get(self, key: &str) -> Outcome<Option<Self>> {
        self.dictionary()?;
        let key = Cf::string(key)?;
        let value = unsafe { CFDictionaryGetValue(self.ptr, key.ptr()) };
        if value.is_null() {
            Ok(None)
        } else {
            Ok(Some(unsafe { self.child(value)? }))
        }
    }
    pub(super) fn array(self, limit: usize) -> Outcome<Vec<Self>> {
        self.expect(unsafe { CFArrayGetTypeID() })?;
        let count = bounded_count(unsafe { CFArrayGetCount(self.ptr) }, limit)?;
        (0..count)
            .map(|i| unsafe { self.child(CFArrayGetValueAtIndex(self.ptr, i as isize)) })
            .collect()
    }
    pub(super) fn text(self) -> Outcome<String> {
        self.expect(unsafe { CFStringGetTypeID() })?;
        let len = bounded_count(unsafe { CFStringGetLength(self.ptr) }, 16384)?;
        let mut bytes = vec![0u8; len * 4 + 1];
        if unsafe {
            CFStringGetCString(
                self.ptr,
                bytes.as_mut_ptr().cast(),
                bytes.len() as isize,
                0x08000100,
            )
        } == 0
        {
            return Err("CFString conversion failed".into());
        }
        CStr::from_bytes_until_nul(&bytes)
            .map_err(|_| "CFString terminator missing")?
            .to_str()
            .map(str::to_owned)
            .map_err(|_| "Invalid CFString UTF-8".into())
    }
    pub(super) fn integer(self) -> Outcome<u64> {
        self.expect(unsafe { CFNumberGetTypeID() })?;
        let mut value = 0i64;
        if unsafe { CFNumberGetValue(self.ptr, 4, ptr::addr_of_mut!(value).cast()) } == 0 {
            return Err("CFNumber integer conversion failed".into());
        }
        u64::try_from(value).map_err(|_| "Negative native integer".into())
    }
    pub(super) fn data(self, limit: usize) -> Outcome<&'a [u8]> {
        self.expect(unsafe { CFDataGetTypeID() })?;
        let len = bounded_count(unsafe { CFDataGetLength(self.ptr) }, limit)?;
        let data = unsafe { CFDataGetBytePtr(self.ptr) };
        if len == 0 {
            return Ok(&[]);
        }
        if data.is_null() {
            return Err("Null CFData bytes".into());
        }
        // SAFETY: checked data object and length; lifetime is tied to the owning CF object.
        Ok(unsafe { std::slice::from_raw_parts(data, len) })
    }
    pub(super) fn metal_name(self) -> Outcome<String> {
        // SAFETY: receiver is a live MTLDevice from MTLCopyAllDevices; selector ABI returns NSString*.
        unsafe {
            let send: unsafe extern "C" fn(Ptr, Ptr) -> Ptr =
                std::mem::transmute(objc_msgSend as unsafe extern "C" fn());
            self.child(send(self.ptr, sel_registerName(c"name".as_ptr())))?
                .text()
        }
    }
    pub(super) fn metal_id(self) -> u64 {
        // SAFETY: MTLDevice registryID returns uint64_t on arm64.
        unsafe {
            let send: unsafe extern "C" fn(Ptr, Ptr) -> u64 =
                std::mem::transmute(objc_msgSend as unsafe extern "C" fn());
            send(self.ptr, sel_registerName(c"registryID".as_ptr()))
        }
    }
    pub(super) fn metal_unified(self) -> bool {
        // SAFETY: MTLDevice hasUnifiedMemory returns Objective-C BOOL (bool on arm64).
        unsafe {
            let send: unsafe extern "C" fn(Ptr, Ptr) -> bool =
                std::mem::transmute(objc_msgSend as unsafe extern "C" fn());
            send(self.ptr, sel_registerName(c"hasUnifiedMemory".as_ptr()))
        }
    }
}

pub(super) struct Io(pub(super) u32);
impl Io {
    pub(super) fn owned(value: u32) -> Outcome<Self> {
        if value == 0 {
            Err("IOKit object absent".into())
        } else {
            Ok(Self(value))
        }
    }
    pub(super) fn name(&self) -> Outcome<String> {
        let mut bytes = [0u8; 128];
        let code = unsafe { IORegistryEntryGetName(self.0, bytes.as_mut_ptr().cast()) };
        check(code, "IORegistryEntryGetName")?;
        text_buffer(&bytes)
    }
    pub(super) fn path(&self, plane: &CStr) -> Outcome<String> {
        let mut bytes = [0u8; 4096];
        let code =
            unsafe { IORegistryEntryGetPath(self.0, plane.as_ptr(), bytes.as_mut_ptr().cast()) };
        check(code, "IORegistryEntryGetPath")?;
        text_buffer(&bytes)
    }
    pub(super) fn id(&self) -> Outcome<u64> {
        let mut id = 0;
        check(
            unsafe { IORegistryEntryGetRegistryEntryID(self.0, &mut id) },
            "IORegistryEntryGetRegistryEntryID",
        )?;
        Ok(id)
    }
    pub(super) fn parent(&self) -> Outcome<Self> {
        let mut value = 0;
        let code =
            unsafe { IORegistryEntryGetParentEntry(self.0, c"IOService".as_ptr(), &mut value) };
        let parent = Self::owned(value);
        check(code, "IORegistryEntryGetParentEntry")?;
        parent
    }
    pub(super) fn property(&self, key: &str) -> Outcome<Option<Cf>> {
        let mut properties = ptr::null();
        let code =
            unsafe { IORegistryEntryCreateCFProperties(self.0, &mut properties, ptr::null(), 0) };
        // Adopt before checking the status so partial native output is released on failure.
        let properties = unsafe { Cf::owned(properties) };
        check(code, "IORegistryEntryCreateCFProperties")?;
        let properties = properties?;
        properties
            .borrow()
            .get(key)?
            .map(|value| {
                // SAFETY: the value remains borrowed from properties until CFRetain gives it an owner.
                unsafe { Cf::owned(CFRetain(value.ptr())) }
            })
            .transpose()
    }
}
impl Drop for Io {
    fn drop(&mut self) {
        unsafe {
            IOObjectRelease(self.0);
        }
    }
}
pub(super) fn check(code: i32, operation: &str) -> Outcome<()> {
    if code == 0 {
        Ok(())
    } else {
        Err(format!("{operation} failed: IOKit return {code:#x}"))
    }
}
fn text_buffer(bytes: &[u8]) -> Outcome<String> {
    CStr::from_bytes_until_nul(bytes)
        .map_err(|_| "Missing native string terminator")?
        .to_str()
        .map(str::to_owned)
        .map_err(|_| "Invalid native UTF-8".into())
}
