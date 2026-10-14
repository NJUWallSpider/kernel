//! Human-readable reformulation proof assembly.
//!
//! `RPA-S 1` versions the source grammar independently of RPX's proof features.
//! This frontend only constructs existing [`Certificate`] values; it neither
//! searches for proofs nor changes their mathematical acceptance conditions.
//! The frozen JSON RPA grammar remains in [`crate::rpa`].

use crate::{model::Model, proof::Certificate};
use serde::Deserialize;
use std::io::{self, Write};

mod checks;
mod format;
mod parse;

pub const HEADER: &str = "RPA-S 1\n";
pub const MAX_SOURCE_BYTES: usize = 256 * 1024 * 1024;
pub const MAX_EXPANDED_NODES: usize = 16_000_000;
pub const MAX_SOURCE_DEPTH: usize = 128;

/// Optional file bindings resolved by the CLI relative to the source file.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelPaths {
    pub source: String,
    pub target: String,
}

/// Parsed source, ready to bind to actual models without parsing it again.
pub struct ParsedSource {
    value: serde_json::Value,
    models: Option<ModelPaths>,
}

impl ParsedSource {
    pub fn declared_models(&self) -> Option<&ModelPaths> {
        self.models.as_ref()
    }
    pub fn assemble(self) -> Result<Certificate, String> {
        self.finish(None)
    }
    pub fn assemble_with_models(
        self,
        source: &Model,
        target: &Model,
    ) -> Result<Certificate, String> {
        self.finish(Some((source, target)))
    }
    fn finish(mut self, models: Option<(&Model, &Model)>) -> Result<Certificate, String> {
        if let Some((source, target)) = models {
            checks::transform(&mut self.value, source, target, checks::Mode::Lower)?;
        } else if checks::contains_named(&self.value) {
            return Err("INVALID RPA source named checks require actual source and target models; use assemble_with_models or declare models for the CLI".into());
        }
        check_expanded_bytes(&self.value)?;
        let certificate: Certificate = serde_json::from_value(self.value)
            .map_err(|error| classify_schema_error(error.to_string()))?;
        crate::codec::certificate_version(&certificate)?;
        Ok(certificate)
    }
}

/// Parse readable source into a complete, unchecked certificate.
///
/// Exact arithmetic, explicit references and all existing proof variants are
/// retained. A successful parse or binary encoding is not proof verification.
pub fn assemble(text: &str) -> Result<Certificate, String> {
    parse(text)?.assemble()
}

/// Bind named checks to complete actual models, then lower them to Ref arrays.
pub fn assemble_with_models(
    text: &str,
    source: &Model,
    target: &Model,
) -> Result<Certificate, String> {
    parse(text)?.assemble_with_models(source, target)
}

/// Parse source and its optional model-file declaration without reading files.
pub fn parse(text: &str) -> Result<ParsedSource, String> {
    if text.len() > MAX_SOURCE_BYTES {
        return Err("RESOURCE_LIMIT RPA source bytes".into());
    }
    let body = text.strip_prefix(HEADER).ok_or_else(|| {
        "INVALID RPA source line 1:1: expected RPA-S 1 header followed by LF".to_string()
    })?;
    let document = parse::parse_document(body)?;
    let models = document
        .models
        .map(serde_json::from_value)
        .transpose()
        .map_err(|error| classify_schema_error(error.to_string()))?;
    Ok(ParsedSource {
        value: document.certificate,
        models,
    })
}

/// Emit deterministic readable source for an existing complete certificate.
pub fn disassemble(certificate: &Certificate) -> Result<String, String> {
    render(certificate, None)
}

/// Render model-bound obligation names, including original variable/row names.
pub fn disassemble_with_models(
    certificate: &Certificate,
    source: &Model,
    target: &Model,
) -> Result<String, String> {
    render(certificate, Some((source, target)))
}

fn render(certificate: &Certificate, models: Option<(&Model, &Model)>) -> Result<String, String> {
    crate::codec::certificate_version(certificate)?;
    let mut value = serde_json::to_value(certificate)
        .map_err(|error| format!("INVALID RPA source output: {error}"))?;
    check_expanded_bytes(&value)?;
    if let Some((source, target)) = models {
        checks::transform(&mut value, source, target, checks::Mode::Name)?;
    }
    check_expanded_bytes(&value)?;
    let body = format::format_value(&value)?;
    drop(value);
    if body.len() > MAX_SOURCE_BYTES - HEADER.len() {
        return Err("RESOURCE_LIMIT RPA source output bytes".into());
    }
    let source = format!("{HEADER}{body}\n");
    // The parser also bounds syntax work and intermediate alias/macro copies.
    // Check that same envelope here so a successful disassembly always emits
    // reassemblable source, including certificates near a resource boundary.
    let recovered = if let Some((input, output)) = models {
        assemble_with_models(&source, input, output)?
    } else {
        assemble(&source)?
    };
    if &recovered != certificate {
        return Err("INVALID RPA source output: round-trip certificate mismatch".into());
    }
    Ok(source)
}

fn classify_schema_error(message: String) -> String {
    let status = if message.contains("RESOURCE_LIMIT") {
        "RESOURCE_LIMIT"
    } else {
        "INVALID"
    };
    format!("{status} RPA source schema: {message}")
}

/// Bound macro expansion by the old text representation's byte budget without
/// allocating a second copy of the fully expanded certificate.
fn check_expanded_bytes(value: &serde_json::Value) -> Result<(), String> {
    expanded_bytes(value).map(|_| ())
}

fn expanded_bytes(value: &serde_json::Value) -> Result<usize, String> {
    struct Counter(usize);
    impl Write for Counter {
        fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
            self.0 = self
                .0
                .checked_add(bytes.len())
                .filter(|count| *count <= MAX_SOURCE_BYTES)
                .ok_or_else(|| io::Error::other("RESOURCE_LIMIT RPA source expanded bytes"))?;
            Ok(bytes.len())
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }
    let mut counter = Counter(0);
    serde_json::to_writer(&mut counter, value)
        .map_err(|error| format!("RESOURCE_LIMIT RPA source expansion: {error}"))?;
    Ok(counter.0)
}
