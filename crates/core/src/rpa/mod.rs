//! Line-oriented RPA 12 proof assembly and disassembly.
//!
//! One logical instruction maps to exactly one wire `Step`, `End`, or
//! `DerivationEnd`. The parser is an untrusted frontend; it produces the same
//! `Certificate` the kernel already consumes and does not validate mathematics.

mod format;
mod parse;

use crate::proof::Certificate;

pub const HEADER: &str = "RPA 12\n";
pub const MAX_SOURCE_BYTES: usize = 256 * 1024 * 1024;
pub const MAX_NODES: usize = 20_000_000;
pub const MAX_DEPTH: usize = 128;

/// Parse RPA 12 text directly into the frozen Certificate schema.
pub fn assemble(text: &str) -> Result<Certificate, String> {
    parse::parse(text)
}

/// Render a Certificate as canonical RPA 12 text.
pub fn disassemble(certificate: &Certificate) -> Result<String, String> {
    format::render(certificate)
}
