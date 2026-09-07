//! Runs on the process main thread, constructs the real production application,
//! and never starts AppKit or opens a window. Run each case in a fresh process.
#[cfg(target_os = "macos")]
#[path = "../src/application.rs"]
mod application;

#[cfg(target_os = "macos")]
fn main() {
    use objc2::rc::{Retained, Weak};
    use objc2::runtime::NSObject;
    use std::{cell::RefCell, panic::AssertUnwindSafe};

    let case = std::env::args()
        .nth(1)
        .unwrap_or_else(|| String::from("success"));
    if case == "background" {
        application::with_application(|app| linked_background_lifetime(&app));
        println!("PASS application lifetime background");
        return;
    }
    let temporary = RefCell::new(None);
    let retained = RefCell::new(None);
    let outcome = std::panic::catch_unwind(AssertUnwindSafe(|| {
        application::with_application(|app| {
            let object = NSObject::new();
            *temporary.borrow_mut() = Some(Weak::from_retained(&object));
            let _ = Retained::autorelease_ptr(object);
            let object = NSObject::new();
            let _ = Retained::autorelease_ptr(object.clone());
            *retained.borrow_mut() = Some(object);
            // The native platform is dropped inside the same production scope.
            drop(app);
            assert!(temporary.borrow().as_ref().unwrap().load().is_some());
            match case.as_str() {
                "success" => Ok(String::from("owned application result")),
                "error" => Err(String::from("owned application error")),
                "unwind" => panic!("intentional application unwind"),
                _ => panic!("unknown lifetime case"),
            }
        })
    }));
    assert!(
        temporary.borrow().as_ref().unwrap().load().is_none(),
        "application scope did not drain its native temporary"
    );
    let object = retained.into_inner().unwrap();
    let weak = Weak::from_retained(&object);
    assert!(
        weak.load().is_some(),
        "explicit retained object died with pool"
    );
    drop(object);
    assert!(weak.load().is_none());
    match case.as_str() {
        "success" => assert_eq!(
            outcome.unwrap(),
            Ok(String::from("owned application result"))
        ),
        "error" => assert_eq!(
            outcome.unwrap(),
            Err(String::from("owned application error"))
        ),
        "unwind" => assert!(outcome.is_err()),
        _ => unreachable!(),
    }
    println!("PASS application lifetime {case}");
}

#[cfg(not(target_os = "macos"))]
fn main() {
    println!("macOS application lifetime cases require native macOS");
}

#[cfg(target_os = "macos")]
fn linked_background_lifetime(app: &gpui::Application) {
    use objc2::{AnyThread, DefinedClass, define_class, msg_send};
    use objc2::{rc::Retained, runtime::NSObject};
    use std::{sync::mpsc, thread::ThreadId, time::Duration};

    define_class!(
        #[unsafe(super(NSObject))]
        #[name = "SystemPulseApplicationWorkerDropProbe"]
        #[ivars = mpsc::Sender<ThreadId>]
        struct WorkerDropProbe;
    );
    impl Drop for WorkerDropProbe {
        fn drop(&mut self) {
            let _ = self.ivars().send(std::thread::current().id());
        }
    }
    let (tx, rx) = mpsc::channel();
    let task = app.background_executor().spawn(async move {
        let object = WorkerDropProbe::alloc().set_ivars(tx);
        // SAFETY: NSObject's init initializes this allocated NSObject subclass.
        let object: Retained<WorkerDropProbe> = unsafe { msg_send![super(object), init] };
        let _ = Retained::autorelease_ptr(object);
        let retained = objc2_foundation::NSString::from_str("retained worker result");
        let _ = Retained::autorelease_ptr(retained.clone());
        (
            std::thread::current().id(),
            retained.to_string(),
            String::from("owned worker result"),
        )
    });
    let destroyed_on = rx
        .recv_timeout(Duration::from_secs(5))
        .expect("linked GPUI background callback did not drain");
    let (ran_on, retained, owned) = smol::block_on(task);
    assert_eq!(destroyed_on, ran_on);
    assert_ne!(ran_on, std::thread::current().id());
    assert_eq!(retained, "retained worker result");
    assert_eq!(owned, "owned worker result");
}
