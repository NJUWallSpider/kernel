//! Pure-Rust core.
//!
//! Invariant: no Python types and no pyo3 dependency in this crate.
#![forbid(unsafe_code)]

const FNV_OFFSET_BASIS: u64 = 0xcbf2_9ce4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01b3;

/// FNV-1a 64-bit hash.
pub fn fnv1a64(data: &[u8]) -> u64 {
    let mut hash = FNV_OFFSET_BASIS;
    for &byte in data {
        hash ^= u64::from(byte);
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}

#[cfg(test)]
mod tests {
    use super::fnv1a64;

    #[test]
    fn reference_vectors() {
        assert_eq!(fnv1a64(b""), 0xcbf2_9ce4_8422_2325);
        assert_eq!(fnv1a64(b"foobar"), 0x8594_4171_f739_67e8);
    }
}

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
