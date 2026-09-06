mod controls;
mod diagnostics;
#[cfg(test)]
mod fixture;
mod live;
mod meters;
#[cfg(test)]
mod native_tests;
mod panel;
mod processes;
mod storage;
pub mod workspace;

mod assets;
mod settings;
pub use assets::install as install_assets;
