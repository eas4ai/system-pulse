//! Compile the exact private production dispatcher source into this test crate.
//! Keeping the vendored package out of the workspace avoids resolving its
//! unrelated benchmark feature and keeps the application's existing lock graph.
#![cfg(target_os = "macos")]

// Match the upstream package's lint for the legacy objc macros in this module.
#[allow(unexpected_cfgs)]
#[path = "../../../vendor/gpui_macos/src/dispatcher.rs"]
mod dispatcher;
