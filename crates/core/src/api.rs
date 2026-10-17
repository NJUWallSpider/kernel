//! Programmatic façade over the kernel: entry points, status classification and
//! the JSON report schema.
//!
//! `main.rs` is a thin shell over this module (identical calls, identical
//! stdout JSON). Services, and the future reformulation compiler, are expected
//! to call these entry points directly instead of driving the CLI through
//! files and text.
//!
//! Invariants of this module:
//! - Verification delegates to the kernel's fixed MI optimization-equivalence
//!   check; this module cannot select a weaker acceptance target.
//! - CLI and library callers receive the same JSON report schema, including
//!   `guarantee: "MI_OPT"` on successful verification.
//! - Failures carry an explicit [`Status`] instead of relying on every caller
//!   re-deriving it from message prefixes.

use crate::{codec, compiler, lp, model, rpa, verify::{self, Limits}};
use serde_json::{json, Value};
use std::{fmt, fs, io::Read, path::Path, time::Instant};

/// Best-effort failure location, re-exported so a caller needs this module only.
pub use crate::verify::{Diagnostics, Location};

/// Direct Certificate JSON resource options, separate from verifier budgets.
pub use crate::compiler::CompileOptions;

/// Maximum bytes read for one input file. Resource policy, not a wire limit;
/// `codec::MAX_FILE_BYTES` and the model/text caps remain the format limits.
pub const MAX_INPUT_BYTES: u64 = 512 * 1024 * 1024;

/// Status word reported on stdout, together with its process exit code.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Status {
    /// Proof verification succeeded.
    Verified,
    /// Model canonicalization succeeded.
    Canonicalized,
    /// RPA 12 text assembly succeeded.
    Assembled,
    /// Structured Certificate JSON encoded directly to RPX.
    Compiled,
    /// Required terminal propositions were enumerated without proving them.
    Planned,
    /// An unchecked candidate proof domain was constructed.
    Prepared,
    /// RPX disassembly succeeded.
    Disassembled,
    /// Model inspection succeeded.
    Inspected,
    /// Model export succeeded.
    Exported,
    /// Input rejected: malformed, mismatched or mathematically invalid.
    Invalid,
    /// A documented resource budget was exhausted. Neither verification nor
    /// refutation.
    ResourceLimit,
    /// Input/output failure.
    IoError,
}

impl Status {
    pub fn as_str(self) -> &'static str {
        match self {
            Status::Verified => "VERIFIED",
            Status::Canonicalized => "CANONICALIZED",
            Status::Assembled => "ASSEMBLED",
            Status::Compiled => "COMPILED",
            Status::Planned => "PLANNED",
            Status::Prepared => "PREPARED",
            Status::Disassembled => "DISASSEMBLED",
            Status::Inspected => "INSPECTED",
            Status::Exported => "EXPORTED",
            Status::Invalid => "INVALID",
            Status::ResourceLimit => "RESOURCE_LIMIT",
            Status::IoError => "IO_ERROR",
        }
    }

    pub fn exit_code(self) -> i32 {
        match self {
            Status::Invalid => 2,
            Status::ResourceLimit => 3,
            Status::IoError => 4,
            _ => 0,
        }
    }

    pub fn is_success(self) -> bool {
        self.exit_code() == 0
    }
}

/// Failure with its status category, the message the CLI has always printed, a
/// short machine-readable code, the verifier location when one is known, and the
/// effective limits when the caller had already parsed them.
#[derive(Clone, Debug)]
pub struct Error {
    status: Status,
    message: String,
    code: String,
    location: Option<Location>,
    limits: Option<Limits>,
}

/// Short code for a failure, derived from the documented message vocabulary.
///
/// The leading status word is dropped; the remaining text is cut at its first
/// delimiter and folded to `snake_case`. Several layers prefix their detail with
/// a single namespace token (`INVALID point: …`, `INVALID flow: …`); when the
/// first phrase is such a lone token, the first two words of the detail are
/// appended so the code stays specific (`point_strictness_witness`). The
/// vocabulary grows with the kernel, so a consumer that needs certainty should
/// read [`Error::status`] and [`Error::location`] and treat the code as a
/// diagnostic aid.
pub fn error_code(status: Status, message: &str) -> String {
    if status == Status::IoError {
        return "io_error".to_owned();
    }
    let body = match message.strip_prefix(status.as_str()) {
        Some(rest) => rest.trim_start_matches([':', ' ']),
        None => message,
    };
    let mut parts = body.split([':', ';', ',', '(', ')', '.', '{', '}', '"', '\'']);
    let phrase = parts.next().unwrap_or("");
    let mut code = fold(phrase);
    // The layers prefix their detail with a single namespace token
    // (`INVALID point: …`); append the first two detail words so the code stays
    // specific. The CLI's own usage error carries no useful detail and keeps the
    // plain `usage` code.
    let lone_namespace = !phrase.contains(char::is_whitespace) && !phrase.trim().is_empty() && phrase != "usage";
    if lone_namespace
        && let Some(detail) = parts.find(|part| !part.trim().is_empty()) {
        let words: Vec<&str> = detail.split_whitespace().take(2).collect();
        if !words.is_empty() {
            code.push('_');
            code.push_str(&fold(&words.join(" ")));
        }
    }
    if code.is_empty() {
        status.as_str().to_ascii_lowercase()
    } else {
        code
    }
}

/// Fold a phrase to `snake_case`: ASCII alphanumerics lowercase, every other run
/// collapsed to a single `_`.
fn fold(phrase: &str) -> String {
    let mut code = String::new();
    let mut separator = false;
    for c in phrase.chars() {
        if c.is_ascii_alphanumeric() {
            if separator && !code.is_empty() {
                code.push('_');
            }
            separator = false;
            code.push(c.to_ascii_lowercase());
        } else {
            separator = true;
        }
    }
    code
}

impl Error {
    /// Classify a message produced by the kernel layers below this façade.
    ///
    /// The layers signal the category with a leading `IO_ERROR` or
    /// `RESOURCE_LIMIT`; anything else is an input rejection. This is the one
    /// place that decision is made, instead of every consumer re-deriving it.
    pub fn from_message(message: String) -> Self {
        let status = if message.starts_with("IO_ERROR") {
            Status::IoError
        } else if message.starts_with("RESOURCE_LIMIT") {
            Status::ResourceLimit
        } else {
            Status::Invalid
        };
        let code = error_code(status, &message);
        Error { status, message, code, location: None, limits: None }
    }

    /// Attach the verifier location. An all-default location is dropped, so the
    /// report never carries an empty `location` object.
    pub fn with_location(mut self, location: Location) -> Self {
        self.location = if location == Location::default() { None } else { Some(location) };
        self
    }

    /// Attach the effective limits, which the CLI echoes on every failure that
    /// happened after argument parsing.
    pub fn with_limits(mut self, limits: Limits) -> Self {
        self.limits = Some(limits);
        self
    }

    pub fn status(&self) -> Status {
        self.status
    }

    pub fn message(&self) -> &str {
        &self.message
    }

    pub fn code(&self) -> &str {
        &self.code
    }

    pub fn location(&self) -> Option<&Location> {
        self.location.as_ref()
    }

    pub fn limits(&self) -> Option<&Limits> {
        self.limits.as_ref()
    }

    /// The single-line failure report: status, message, code, the location when
    /// the verifier attributed one, and the effective limits when known.
    pub fn to_json(&self) -> Value {
        let mut value = json!({
            "status": self.status.as_str(),
            "message": self.message,
            "code": self.code,
        });
        if let Some(location) = &self.location {
            value["location"] = json!(location);
        }
        if let Some(limits) = &self.limits {
            value["limits"] = limits_json(limits);
        }
        value
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for Error {}

impl From<String> for Error {
    fn from(message: String) -> Self {
        Error::from_message(message)
    }
}

/// Effective budgets as reported in every success and failure report.
pub fn limits_json(limits: &Limits) -> Value {
    json!({"work": limits.work, "live_facts": limits.live_facts, "depth": limits.depth})
}

/// Phase timings of one entry-point call, in microseconds.
#[derive(Clone, Copy, Debug, Default)]
pub struct Timings {
    /// Absent when the caller supplied bytes or text instead of paths.
    pub read_us: Option<u128>,
    pub model_decode_us: u128,
    pub proof_decode_us: u128,
    pub execute_us: u128,
}

/// Read one input file under the CLI file-size policy.
pub fn read_input(path: &str) -> Result<Vec<u8>, Error> {
    let file = fs::File::open(path).map_err(|e| Error::from_message(format!("IO_ERROR {path}: {e}")))?;
    let len = file.metadata().map_err(|e| Error::from_message(format!("IO_ERROR {e}")))?.len();
    if len > MAX_INPUT_BYTES {
        return Err(Error::from_message("RESOURCE_LIMIT input file bytes".into()));
    }
    let mut bytes = Vec::new();
    bytes.try_reserve(len as usize).map_err(|_| Error::from_message("RESOURCE_LIMIT file allocation".into()))?;
    file.take(MAX_INPUT_BYTES + 1).read_to_end(&mut bytes).map_err(|e| Error::from_message(format!("IO_ERROR {e}")))?;
    if bytes.len() as u64 > MAX_INPUT_BYTES {
        return Err(Error::from_message("RESOURCE_LIMIT input file bytes".into()));
    }
    Ok(bytes)
}

/// Read one UTF-8 input file.
pub fn read_text(path: &str) -> Result<String, Error> {
    String::from_utf8(read_input(path)?).map_err(|_| Error::from_message("INVALID non-UTF8 text".into()))
}

/// Write one output file. Parent directories are created; the file is replaced
/// only after the caller has fully produced its bytes.
pub fn write_output(path: &str, bytes: &[u8]) -> Result<(), Error> {
    let path = Path::new(path);
    if let Some(parent) = path.parent()
        && !parent.as_os_str().is_empty() {
        fs::create_dir_all(parent).map_err(|e| Error::from_message(format!("IO_ERROR {e}")))?;
    }
    fs::write(path, bytes).map_err(|e| Error::from_message(format!("IO_ERROR {e}")))
}

/// Canonicalize a trusted MPS/LP file into an MCM file.
pub fn canonicalize_path(input: &str, output: &str) -> Result<Value, Error> {
    let start = Instant::now();
    let text = read_text(input)?;
    let read_us = start.elapsed().as_micros();
    let parsed = if Path::new(input).extension().is_some_and(|s| s.eq_ignore_ascii_case("lp")) {
        lp::parse_lp(&text)?
    } else {
        model::parse_mps(&text)?
    };
    let parse_us = start.elapsed().as_micros() - read_us;
    let encoded = codec::encode_model(&parsed)?;
    write_output(output, &encoded)?;
    Ok(json!({
        "status": Status::Canonicalized.as_str(),
        "variables": parsed.vars.len(),
        "rows": parsed.rows.len(),
        "mcm_bytes": encoded.len(),
        "read_us": read_us,
        "parse_us": parse_us,
        "total_us": start.elapsed().as_micros(),
    }))
}

/// Assemble RPA 12 text directly into an RPX file.
pub fn assemble_paths(input: &str, output: &str) -> Result<Value, Error> {
    let start = Instant::now();
    let text = read_text(input)?;
    let certificate = rpa::assemble(&text)?;
    let encoded = codec::encode_certificate(&certificate)?;
    write_output(output, &encoded)?;
    Ok(json!({
        "status": Status::Assembled.as_str(),
        "rpx_bytes": encoded.len(),
        "total_us": start.elapsed().as_micros(),
    }))
}

/// Direct structured proof compilation. No RPA parser or assembly is involved.
pub fn compile_certificate_json(text: &str) -> Result<Vec<u8>, Error> {
    compile_certificate_json_with_options(text, &CompileOptions::default())
}

/// Direct compilation under an explicit Certificate JSON byte budget. RPX
/// codec limits and verification rules/budgets are unaffected.
pub fn compile_certificate_json_with_options(text: &str, options: &CompileOptions) -> Result<Vec<u8>, Error> {
    Ok(compiler::compile_certificate_json_with_options(text, options)?)
}

// Keep Certificate reads separate: changing a compile budget must not widen
// canonical/model/RPX reads through the general MAX_INPUT_BYTES policy.
fn read_certificate_json_from(reader: impl Read, reported_len: u64, options: &CompileOptions) -> Result<String, Error> {
    options.validate()?;
    let limit = options.max_json_bytes;
    if reported_len > limit {
        return Err(Error::from_message("RESOURCE_LIMIT input file bytes".into()));
    }
    let length = usize::try_from(reported_len)
        .map_err(|_| Error::from_message("RESOURCE_LIMIT file allocation".into()))?;
    let mut bytes = Vec::new();
    bytes.try_reserve(length).map_err(|_| Error::from_message("RESOURCE_LIMIT file allocation".into()))?;
    // A file can grow after metadata is read. Read one extra byte to detect it.
    // At u64::MAX the saturating bound cannot wrap; no supported Vec can hold
    // more than that many bytes, and the actual length is independently tested.
    reader.take(limit.saturating_add(1)).read_to_end(&mut bytes)
        .map_err(|e| Error::from_message(format!("IO_ERROR {e}")))?;
    if bytes.len() as u128 > u128::from(limit) {
        return Err(Error::from_message("RESOURCE_LIMIT input file bytes".into()));
    }
    String::from_utf8(bytes).map_err(|_| Error::from_message("INVALID non-UTF8 text".into()))
}

fn read_certificate_json_path(input: &str, options: &CompileOptions) -> Result<String, Error> {
    let file = fs::File::open(input).map_err(|e| Error::from_message(format!("IO_ERROR {input}: {e}")))?;
    let len = file.metadata().map_err(|e| Error::from_message(format!("IO_ERROR {e}")))?.len();
    read_certificate_json_from(file, len, options)
}

/// Encode raw Certificate JSON to an RPX file. Compilation checks wire/schema
/// validity; correctness is established separately by [`verify_paths`].
pub fn compile_certificate_paths(input: &str, output: &str) -> Result<Value, Error> {
    compile_certificate_paths_with_options(input, output, &CompileOptions::default())
}

/// Encode a Certificate with an explicit JSON read/parse budget, preserving
/// the general file policy and all independent RPX and verification limits.
pub fn compile_certificate_paths_with_options(input: &str, output: &str, options: &CompileOptions) -> Result<Value, Error> {
    options.validate()?;
    let start = Instant::now();
    let encoded = compile_certificate_json_with_options(&read_certificate_json_path(input, options)?, options)?;
    write_output(output, &encoded)?;
    Ok(json!({"status": Status::Compiled.as_str(), "rpx_bytes": encoded.len(),
        "version": u16::from_le_bytes([encoded[4], encoded[5]]),
        "compile_limits": {"certificate_json_bytes": options.max_json_bytes},
        "total_us": start.elapsed().as_micros()}))
}

/// Plan a Return with already-oriented current input/output MCM models. Write
/// the ordered proposition array; each item includes its model/objective origin.
pub fn plan_return_paths(input: &str, output: &str, plan: &str, obligations: &str) -> Result<Value, Error> {
    let start = Instant::now();
    let input = codec::decode_model(&read_input(input)?)?;
    let output = codec::decode_model(&read_input(output)?)?;
    let plan = compiler::parse_return_plan_json(&read_text(plan)?)?;
    let planned = compiler::plan_return(&input, &output, &plan, &Limits::default())?;
    let mut text = serde_json::to_string_pretty(&planned)
        .map_err(|error| Error::from_message(format!("INVALID Return plan output: {error}")))?;
    text.push('\n');
    write_output(obligations, text.as_bytes())?;
    Ok(json!({"status": Status::Planned.as_str(), "obligations": planned.len(),
        "json_bytes": text.len(), "total_us": start.elapsed().as_micros()}))
}

/// Mechanically reuse exact model/local propositions for Return. This is an
/// authoring convenience; the Kernel independently executes every proof step.
pub fn resolve_return_paths(input: &str, output: &str, spec: &str, result: &str) -> Result<Value, Error> {
    let start=Instant::now();
    let input=codec::decode_model(&read_input(input)?)?;
    let output=codec::decode_model(&read_input(output)?)?;
    let resolved=compiler::resolve_return_json(&input,&output,&read_text(spec)?,&Limits::default())?;
    let text=serde_json::to_vec(&resolved).map_err(|e|Error::from_message(format!("INVALID resolve Return output: {e}")))?;
    write_output(result,&text)?;
    Ok(json!({"status":Status::Planned.as_str(),"obligations":resolved.obligations,"missing":resolved.missing.len(),
        "json_bytes":text.len(),"total_us":start.elapsed().as_micros()}))
}


/// Disassemble an RPX file back into canonical RPA 12 text.
pub fn disassemble_paths(input: &str, output: &str) -> Result<Value, Error> {
    let certificate = codec::decode_certificate(&read_input(input)?)?;
    write_output(output, rpa::disassemble(&certificate)?.as_bytes())?;
    Ok(json!({"status": Status::Disassembled.as_str()}))
}

/// Report one MCM file's shape without revealing its contents.
pub fn inspect_model_path(input: &str) -> Result<Value, Error> {
    let parsed = codec::decode_model(&read_input(input)?)?;
    Ok(json!({
        "status": Status::Inspected.as_str(),
        "name": parsed.name,
        "variables": parsed.vars.len(),
        "rows": parsed.rows.len(),
        "integers": parsed.vars.iter().filter(|v| v.integer).count(),
        "nonzeros": parsed.rows.iter().map(|r| r.expr.terms.len()).sum::<usize>() + parsed.objective.terms.len(),
    }))
}

/// Export one MCM file as canonical model JSON. The schema and the scalar
/// grammar are documented in `docs/API.md`; `model::to_json` owns the format.
pub fn export_model_paths(input: &str, output: &str) -> Result<Value, Error> {
    let start = Instant::now();
    let parsed = codec::decode_model(&read_input(input)?)?;
    let model_json = model::to_json(&parsed);
    let mut text = serde_json::to_string_pretty(&model_json)
        .map_err(|e| Error::from_message(format!("INVALID model json: {e}")))?;
    text.push('\n');
    write_output(output, text.as_bytes())?;
    Ok(json!({
        "status": Status::Exported.as_str(),
        "name": parsed.name,
        "variables": parsed.vars.len(),
        "rows": parsed.rows.len(),
        "json_bytes": text.len(),
        "total_us": start.elapsed().as_micros(),
    }))
}

/// Verify MI optimization equivalence using one RPX file on a complete MCM
/// model pair. Both directions share one verification work budget.
pub fn verify_paths(source: &str, target: &str, proof: &str, limits: &Limits) -> Result<Value, Error> {
    let start = Instant::now();
    let source_bytes = read_input(source)?;
    let target_bytes = read_input(target)?;
    let proof_bytes=read_input(proof)?;
    verify_bytes_at(&source_bytes,&target_bytes,&proof_bytes,limits,Some(start.elapsed().as_micros()),start)
}

/// Filesystem-free counterpart of `verify_paths` with identical MI_OPT semantics.
pub fn verify_bytes(source: &[u8], target: &[u8], proof: &[u8], limits: &Limits) -> Result<Value, Error> {
    verify_bytes_at(source, target, proof, limits, None, Instant::now())
}

fn verify_bytes_at(source: &[u8], target: &[u8], proof: &[u8], limits: &Limits, read_us: Option<u128>, start: Instant) -> Result<Value, Error> {
    let decoded_since_read = Instant::now();
    let source_model = codec::decode_model(source)?;
    let target_model = codec::decode_model(target)?;
    let model_decode_us = decoded_since_read.elapsed().as_micros();
    let certificate=codec::decode_certificate(proof)?;
    let proof_decode_us = decoded_since_read.elapsed().as_micros() - model_decode_us;
    let mut diagnostics = Diagnostics::default();
    let statistics = verify::verify_with_diagnostics(&source_model,&target_model,&certificate,limits,&mut diagnostics)
        .map_err(|message| Error::from_message(message).with_location(diagnostics.location))?;
    let execute_us = decoded_since_read.elapsed().as_micros() - model_decode_us - proof_decode_us;
    Ok(verify_report(&statistics, limits, &Timings { read_us, model_decode_us, proof_decode_us, execute_us }, start))
}

/// The verification report: fixed guarantee, verification statistics,
/// effective limits and phase timings.
fn verify_report(statistics: &verify::Statistics, limits: &Limits, timings: &Timings, start: Instant) -> Value {
    let mut result = json!({
        "status": Status::Verified.as_str(),
        "guarantee": "MI_OPT",
        "statistics": statistics,
        "limits": limits_json(limits),
        "model_decode_us": timings.model_decode_us,
        "proof_decode_us": timings.proof_decode_us,
        "execute_us": timings.execute_us,
        "total_us": start.elapsed().as_micros(),
    });
    if let Some(read_us) = timings.read_us {
        result["read_us"] = json!(read_us);
    }
    result
}

#[cfg(test)]
mod compile_input_tests {
    use super::*;
    use std::io::{self, Cursor};

    struct MustNotRead;
    impl Read for MustNotRead {
        fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
            panic!("invalid budget or excessive metadata must be rejected before reading")
        }
    }

    #[test]
    fn certificate_reader_checks_declared_and_actual_length_independently() {
        let options = CompileOptions::new(3).unwrap();
        assert_eq!(read_certificate_json_from(Cursor::new(b"abc"), 3, &options).unwrap(), "abc");
        let early = read_certificate_json_from(MustNotRead, 4, &options).unwrap_err();
        assert_eq!(early.status(), Status::ResourceLimit);
        // Simulate a stream/file growing after its metadata was sampled.
        let late = read_certificate_json_from(Cursor::new(b"abcd-extra"), 0, &options).unwrap_err();
        assert_eq!(late.status(), Status::ResourceLimit);
        assert!(late.message().contains("input file bytes"));
    }

    #[test]
    fn certificate_reader_maximum_budget_does_not_wrap_or_preallocate_the_budget() {
        let options = CompileOptions::new(u64::MAX).unwrap();
        assert_eq!(read_certificate_json_from(Cursor::new(b"abc"), 0, &options).unwrap(), "abc");
        let zero = CompileOptions { max_json_bytes: 0 };
        assert_eq!(read_certificate_json_from(MustNotRead, 0, &zero).unwrap_err().status(), Status::Invalid);
        assert_eq!(read_certificate_json_from(Cursor::new([0xff_u8]), 1, &options).unwrap_err().status(), Status::Invalid);
    }
}
