//! Observe real Objective-C object lifetime; a no-op pool cannot satisfy these checks.
use super::ffi::{AutoreleasePool, Cf};
use std::{
    ffi::{c_char, c_void},
    panic::{AssertUnwindSafe, catch_unwind},
    ptr,
};
type Object = *mut c_void;
#[link(name = "Foundation", kind = "framework")]
unsafe extern "C" {}
#[link(name = "objc")]
unsafe extern "C" {
    fn objc_getClass(name: *const c_char) -> Object;
    fn class_createInstance(class: Object, extra_bytes: usize) -> Object;
    fn objc_autorelease(object: Object) -> Object;
    fn objc_initWeak(location: *mut Object, object: Object) -> Object;
    fn objc_loadWeakRetained(location: *mut Object) -> Object;
    fn objc_destroyWeak(location: *mut Object);
    fn objc_release(object: Object);
}
// The runtime registers the slot address, so the slot must not move with this Rust value.
struct WeakObject {
    slot: Box<Object>,
}
impl WeakObject {
    fn autoreleased() -> Self {
        let mut slot = Box::new(ptr::null_mut());
        // SAFETY: NSObject is loaded by Foundation; create returns a +1 instance.
        // A weak reference adds no ownership. Autorelease schedules that +1 for the current pool.
        unsafe {
            let class = objc_getClass(c"NSObject".as_ptr());
            assert!(!class.is_null());
            let object = class_createInstance(class, 0);
            assert!(!object.is_null());
            assert_eq!(objc_initWeak(&mut *slot, object), object);
            objc_autorelease(object);
        }
        Self { slot }
    }
    fn is_alive(&mut self) -> bool {
        // SAFETY: slot is initialized and stationary; balance the temporary strong reference.
        unsafe {
            let object = objc_loadWeakRetained(&mut *self.slot);
            let alive = !object.is_null();
            objc_release(object);
            alive
        }
    }
}
impl Drop for WeakObject {
    fn drop(&mut self) {
        unsafe { objc_destroyWeak(&mut *self.slot) }
    }
}
#[test]
fn pool_drains_real_objects_on_normal_return_early_return_and_unwind() {
    let mut normal;
    {
        let _pool = AutoreleasePool::new();
        normal = WeakObject::autoreleased();
        assert!(
            normal.is_alive(),
            "weak witness must observe an object before pool drainage"
        );
    }
    assert!(
        !normal.is_alive(),
        "normal return must drain the native pool"
    );

    fn early_return(stop: bool) -> Result<(), WeakObject> {
        let _pool = AutoreleasePool::new();
        let mut object = WeakObject::autoreleased();
        assert!(object.is_alive());
        if stop {
            return Err(object);
        }
        Ok(())
    }
    let mut early = early_return(true).expect_err("exercise early error return");
    assert!(!early.is_alive(), "early return must drain the native pool");

    let mut unwound = None;
    let panic = catch_unwind(AssertUnwindSafe(|| {
        let _pool = AutoreleasePool::new();
        let mut object = WeakObject::autoreleased();
        assert!(object.is_alive());
        unwound = Some(object);
        panic!("exercise native pool cleanup during Rust unwinding");
    }));
    assert!(panic.is_err());
    assert!(
        !unwound.unwrap().is_alive(),
        "unwinding must drain the native pool"
    );
}
#[test]
fn retained_cf_and_owned_rust_values_survive_pool_drainage() {
    let (owned_cf, owned_rust) = {
        let _pool = AutoreleasePool::new();
        let cf = Cf::string("retained across capture pools").unwrap();
        let copied = cf.borrow().text().unwrap();
        (cf, copied)
    };
    assert_eq!(owned_cf.borrow().text().unwrap(), owned_rust);
    assert_eq!(owned_rust, "retained across capture pools");
}
