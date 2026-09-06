use super::*;
use futures::{FutureExt, executor::block_on, future::poll_fn};
use objc2::rc::{Retained, Weak, autoreleasepool};
use objc2::runtime::NSObject;
use objc2::{AnyThread, DefinedClass, define_class, msg_send};
use std::{cell::Cell, rc::Rc, task::Poll};

fn invoke(runnable: RunnableVariant) {
    trampoline(runnable.into_raw().as_ptr().cast());
}

#[test]
fn callback_drains_temporary_and_preserves_retained_and_owned_result() {
    autoreleasepool(|_| {
        let (runnable, task) = async_task::Builder::new()
            .metadata(RunnableMeta::new_with_callers_location())
            .spawn_local(
                |_| async {
                    let temporary = NSObject::new();
                    let weak = Weak::from_retained(&temporary);
                    let _ = Retained::autorelease_ptr(temporary);
                    let retained = NSObject::new();
                    let _ = Retained::autorelease_ptr(retained.clone());
                    (weak, retained, String::from("owned callback result"))
                },
                |_| unreachable!("ready callback must not reschedule"),
            );
        invoke(runnable);
        let (temporary, retained, owned) = block_on(task);
        assert!(
            temporary.load().is_none(),
            "callback temporary survived invocation"
        );
        assert_eq!(owned, "owned callback result");
        let weak = Weak::from_retained(&retained);
        assert!(weak.load().is_some());
        drop(retained);
        assert!(
            weak.load().is_none(),
            "pool retained an extra native reference"
        );
    });
}

#[test]
fn callback_drains_on_error_result() {
    autoreleasepool(|_| {
        let (runnable, task) = async_task::Builder::new()
            .metadata(RunnableMeta::new_with_callers_location())
            .spawn_local(
                |_| async {
                    let object = NSObject::new();
                    let weak = Weak::from_retained(&object);
                    let _ = Retained::autorelease_ptr(object);
                    (weak, Err::<(), _>(String::from("native operation failed")))
                },
                |_| unreachable!(),
            );
        invoke(runnable);
        let (temporary, result) = block_on(task);
        assert!(temporary.load().is_none(), "error callback did not drain");
        assert_eq!(result.unwrap_err(), "native operation failed");
    });
}

#[test]
fn each_pending_poll_drains_before_the_next_invocation() {
    autoreleasepool(|_| {
        let polls = Rc::new(Cell::new(0));
        let temporaries = Rc::new(std::cell::RefCell::new(Vec::new()));
        let (tx, rx) = std::sync::mpsc::channel();
        let (runnable, task) = async_task::Builder::new()
            .metadata(RunnableMeta::new_with_callers_location())
            .spawn_local(
                {
                    let polls = polls.clone();
                    let temporaries = temporaries.clone();
                    move |_| {
                        poll_fn(move |cx| {
                            let object = NSObject::new();
                            temporaries.borrow_mut().push(Weak::from_retained(&object));
                            let _ = Retained::autorelease_ptr(object);
                            polls.set(polls.get() + 1);
                            if polls.get() == 1 {
                                cx.waker().wake_by_ref();
                                Poll::Pending
                            } else {
                                Poll::Ready(String::from("completed second poll"))
                            }
                        })
                    }
                },
                move |runnable| tx.send(runnable).unwrap(),
            );
        invoke(runnable);
        assert!(
            temporaries.borrow()[0].load().is_none(),
            "pending poll did not drain"
        );
        invoke(rx.recv_timeout(Duration::from_secs(5)).unwrap());
        assert!(
            temporaries.borrow()[1].load().is_none(),
            "second poll did not drain"
        );
        assert_eq!(block_on(task), "completed second poll");
        assert_eq!(polls.get(), 2);
    });
}

#[test]
fn canceled_runnable_drains_native_temporaries_created_by_future_drop() {
    struct OnDrop(Rc<std::cell::RefCell<Option<Weak<NSObject>>>>);
    impl Drop for OnDrop {
        fn drop(&mut self) {
            let object = NSObject::new();
            *self.0.borrow_mut() = Some(Weak::from_retained(&object));
            let _ = Retained::autorelease_ptr(object);
        }
    }
    autoreleasepool(|_| {
        let temporary = Rc::new(std::cell::RefCell::new(None));
        let guard = OnDrop(temporary.clone());
        let (runnable, task) = async_task::Builder::new()
            .metadata(RunnableMeta::new_with_callers_location())
            .spawn_local(
                move |_| async move {
                    let _guard = guard;
                    std::future::pending::<()>().await;
                },
                |_| unreachable!(),
            );
        drop(task);
        invoke(runnable);
        assert!(
            temporary.borrow().as_ref().unwrap().load().is_none(),
            "canceled future drop escaped callback pool"
        );
    });
}

define_class!(
    #[unsafe(super(NSObject))]
    #[name = "SystemPulseDispatcherDropProbe"]
    #[ivars = std::sync::mpsc::Sender<std::thread::ThreadId>]
    struct DropProbe;
);

impl DropProbe {
    fn new(sender: std::sync::mpsc::Sender<std::thread::ThreadId>) -> Retained<Self> {
        let object = Self::alloc().set_ivars(sender);
        // SAFETY: NSObject's init initializes this allocated NSObject subclass.
        unsafe { msg_send![super(object), init] }
    }
}

impl Drop for DropProbe {
    fn drop(&mut self) {
        // A failed regression may have already dropped the receiver. Destruction
        // must not panic across Objective-C's dealloc boundary.
        let _ = self.ivars().send(std::thread::current().id());
    }
}

#[test]
fn native_background_and_delayed_dispatch_drain_on_the_callback_thread() {
    for mode in 0..4 {
        let (destroyed_tx, destroyed_rx) = std::sync::mpsc::channel();
        let (runnable, task) = async_task::Builder::new()
            .metadata(RunnableMeta::new_with_callers_location())
            .spawn(
                move |_| async move {
                    let _ = Retained::autorelease_ptr(DropProbe::new(destroyed_tx));
                    let info = objc2_foundation::NSProcessInfo::processInfo();
                    (
                        std::thread::current().id(),
                        info.operatingSystemVersionString().to_string(),
                    )
                },
                |_| unreachable!(),
            );
        let dispatcher = MacDispatcher::new();
        match mode {
            0 => dispatcher.dispatch(runnable, Priority::High),
            1 => dispatcher.dispatch(runnable, Priority::Medium),
            2 => dispatcher.dispatch(runnable, Priority::Low),
            _ => dispatcher.dispatch_after(Duration::from_millis(1), runnable),
        }
        let destroyed_on = destroyed_rx
            .recv_timeout(Duration::from_secs(5))
            .expect("native callback did not drain its autoreleased object");
        let (ran_on, owned) = task
            .now_or_never()
            .expect("callback has finished before pool drains");
        assert_eq!(destroyed_on, ran_on);
        assert_ne!(ran_on, std::thread::current().id());
        assert!(!owned.is_empty());
    }
}
