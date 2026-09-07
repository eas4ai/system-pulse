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

mod layout;

mod panel_context;

mod dashboard;

mod screen_charts;
mod screen_data;
mod screen_pages;
mod screen_style;
mod screen_summary;
#[cfg(test)]
mod screen_tests;
pub mod screens;
pub mod tray;
