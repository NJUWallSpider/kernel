//! Pure-Rust exact-reformulation kernel.
//!
//! Invariants:
//! - no `unsafe` code, no Python types, no solver, no dynamic theorem plugin;
//! - the library never reads the environment, the clock or the filesystem on the
//!   verification path; [`api`] isolates the file-based entry points.
#![forbid(unsafe_code)]

/// Programmatic façade: entry points, status classification, JSON reports.
pub mod api;

pub mod model;
pub mod proof;
pub mod verify;
pub mod codec;
pub mod rpa;

pub mod lp;
pub mod point;
pub mod flow;
pub mod subflow;
pub mod interval;
pub mod menu;
pub mod injectivity;

pub mod signed;
pub mod level;

mod build_support;
