//! Isolated proposed subflow builder. No production opcode/format registration.
pub use kernel_core::model;
pub use kernel_core::verify;
#[path = "../../checkpoints/delivery-78-working-source/crates/core/src/build_support.rs"]
mod build_support;
pub mod proof {
    use crate::model::{Expr, Q};
    pub use kernel_core::proof::{Kind, Ref};
    #[derive(Clone, Debug, PartialEq, Eq)]
    pub struct SubflowGroup {
        pub source: u32,
        pub demands: Vec<(u32, Q)>,
        pub flows: Vec<Expr>,
        pub nonnegative: Vec<Ref>,
        pub balances: Vec<Ref>,
    }
    #[derive(Clone, Debug, PartialEq, Eq)]
    pub struct SubflowWitness {
        pub nodes: u32,
        pub arcs: Vec<(u32, u32)>,
        pub groups: Vec<SubflowGroup>,
    }
}
pub mod subflow;
