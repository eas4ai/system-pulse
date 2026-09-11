pub mod counters;
mod types;
pub use types::*;
mod host;
pub use host::HostCollector;
#[cfg(target_os = "linux")]
mod intel;
mod nvidia;
pub mod process_control;
mod service;
#[cfg(any(test, target_os = "windows"))]
mod windows_energy;
#[cfg(any(test, target_os = "windows"))]
mod windows_gpu;
pub mod windows_thermal;
pub use service::{DEFAULT_INTERVAL, SUPPORTED_INTERVALS, SamplingService};

#[cfg(any(test, all(target_os = "macos", target_arch = "aarch64")))]
mod apple;
