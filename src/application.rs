/// Scope native construction and the caller's orderly application teardown.
/// Owned callback results can outlive the pool; borrowed native temporaries cannot.
pub(crate) fn with_application<T>(run: impl FnOnce(gpui::Application) -> T) -> T {
    #[cfg(target_os = "macos")]
    {
        objc2::rc::autoreleasepool(|_| run(gpui_platform::application()))
    }
    #[cfg(not(target_os = "macos"))]
    {
        run(gpui_platform::application())
    }
}
