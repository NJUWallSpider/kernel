//! Certificate JSON budgets affect only read/parse policy, not the RPX proof.
use kernel_core::{api, codec, compiler, model::Q, proof::{Block, Certificate, End}};
use num_bigint::BigInt;
use serde_json::{json, Value};
use std::{fs, path::{Path, PathBuf}, process::Command, sync::atomic::{AtomicUsize, Ordering}};

static SEQUENCE: AtomicUsize = AtomicUsize::new(0);
struct Temp(PathBuf);
impl Temp {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!("rpx-compile-limits-{}-{}",
            std::process::id(), SEQUENCE.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir_all(&path).unwrap();
        Self(path)
    }
}
impl Drop for Temp { fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0); } }

fn vector() -> Vec<u8> {
    fs::read(Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/vectors/identity-ordinary.rpx")).unwrap()
}
fn certificate() -> Certificate { codec::decode_certificate(&vector()).unwrap() }

#[test]
fn typed_json_budget_has_an_exact_boundary_and_default_delegation() {
    let cert = certificate();
    let text = serde_json::to_string(&cert).unwrap();
    let exact = compiler::CompileOptions::new(text.len() as u64).unwrap();
    assert_eq!(compiler::parse_certificate_json_with_options(&text, &exact).unwrap(), cert);
    assert_eq!(api::compile_certificate_json_with_options(&text, &exact).unwrap(), vector());
    assert_eq!(api::compile_certificate_json(&text).unwrap(), vector());
    assert_eq!(compiler::compile_certificate_json(&text).unwrap(), vector());
    let too_small = compiler::CompileOptions::new(text.len() as u64 - 1).unwrap();
    let error = api::compile_certificate_json_with_options(&text, &too_small).unwrap_err();
    assert_eq!(error.status(), api::Status::ResourceLimit);
    assert!(error.message().contains("certificate JSON bytes"));
    assert!(compiler::CompileOptions::new(0).unwrap_err().starts_with("INVALID"));
    let zero = compiler::CompileOptions { max_json_bytes: 0 };
    assert_eq!(api::compile_certificate_json_with_options(&text, &zero).unwrap_err().status(), api::Status::Invalid);
    let maximum = compiler::CompileOptions::new(u64::MAX).unwrap();
    assert_eq!(api::compile_certificate_json_with_options(&text, &maximum).unwrap(), vector());
}

#[test]
fn file_budget_reports_effective_limit_and_preserves_output_on_failure() {
    let dir = Temp::new();
    let input = dir.0.join("certificate.json");
    let output = dir.0.join("proof.rpx");
    let text = serde_json::to_string(&certificate()).unwrap();
    fs::write(&input, &text).unwrap();
    let report = api::compile_certificate_paths(input.to_str().unwrap(), output.to_str().unwrap()).unwrap();
    assert_eq!(report["status"], "COMPILED");
    assert_eq!(report["compile_limits"], json!({"certificate_json_bytes": 1024_u64 * 1024 * 1024}));
    // Sparse metadata only: the general reader must still stop at 512 MiB,
    // before reading or allocating the file body. No large fixture is needed.
    let general_input = dir.0.join("general-input.bin");
    fs::File::create(&general_input).unwrap().set_len(512 * 1024 * 1024 + 1).unwrap();
    assert_eq!(api::read_input(general_input.to_str().unwrap()).unwrap_err().status(), api::Status::ResourceLimit);
    let options = api::CompileOptions::new(text.len() as u64).unwrap();
    let report = api::compile_certificate_paths_with_options(input.to_str().unwrap(), output.to_str().unwrap(), &options).unwrap();
    assert_eq!(report["compile_limits"], json!({"certificate_json_bytes": text.len()}));
    assert_eq!(fs::read(&output).unwrap(), vector());
    let too_small = api::CompileOptions::new(text.len() as u64 - 1).unwrap();
    let error = api::compile_certificate_paths_with_options(input.to_str().unwrap(), output.to_str().unwrap(), &too_small).unwrap_err();
    assert_eq!(error.status(), api::Status::ResourceLimit);
    assert!(error.message().contains("input file bytes"));
    assert_eq!(fs::read(output).unwrap(), vector());
}

#[test]
fn cli_budget_is_explicit_order_independent_and_overflow_safe() {
    let dir = Temp::new();
    let input = dir.0.join("certificate.json");
    let output = dir.0.join("proof.rpx");
    let text = serde_json::to_string(&certificate()).unwrap();
    fs::write(&input, &text).unwrap();
    let input = input.to_str().unwrap();
    let output = output.to_str().unwrap();
    let budget = text.len().to_string();
    for arguments in [
        vec!["--max-json-bytes", budget.as_str(), input, output],
        vec![input, "--max-json-bytes", budget.as_str(), output],
        vec![input, output, "--max-json-bytes", budget.as_str()],
    ] {
        let result = Command::new(env!("CARGO_BIN_EXE_rpx")).arg("compile").args(arguments).output().unwrap();
        assert!(result.status.success(), "{}", String::from_utf8_lossy(&result.stdout));
        let report: Value = serde_json::from_slice(&result.stdout).unwrap();
        assert_eq!(report["compile_limits"], json!({"certificate_json_bytes": text.len()}));
        assert_eq!(fs::read(output).unwrap(), vector());
    }
    let maximum = u64::MAX.to_string();
    let result = Command::new(env!("CARGO_BIN_EXE_rpx")).arg("compile")
        .args(["--max-json-bytes", maximum.as_str(), input, output]).output().unwrap();
    assert!(result.status.success(), "{}", String::from_utf8_lossy(&result.stdout));
    let report: Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["compile_limits"]["certificate_json_bytes"], json!(u64::MAX));

    let result = Command::new(env!("CARGO_BIN_EXE_rpx")).arg("compile")
        .args(["--max-json-bytes", "1", input, output]).output().unwrap();
    assert_eq!(result.status.code(), Some(3));
    let report: Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["status"], "RESOURCE_LIMIT");
    assert_eq!(fs::read(output).unwrap(), vector());

    for flags in [
        vec!["--max-json-bytes"],
        vec!["--max-json-bytes", ""],
        vec!["--max-json-bytes", "0"],
        vec!["--max-json-bytes", "-1"],
        vec!["--max-json-bytes", "+1"],
        vec!["--max-json-bytes", "1.5"],
        vec!["--max-json-bytes", "1e9"],
        vec!["--max-json-bytes", "18446744073709551616"],
        vec!["--max-json-bytes", "8", "--max-json-bytes", "16"],
        vec!["--unknown", "16"],
        vec!["--max-json-bytes=16"],
    ] {
        let result = Command::new(env!("CARGO_BIN_EXE_rpx")).arg("compile")
            .args([input, output]).args(&flags).output().unwrap();
        assert_eq!(result.status.code(), Some(2), "{flags:?}");
        let report: Value = serde_json::from_slice(&result.stdout).unwrap();
        assert_eq!(report["status"], "INVALID", "{flags:?}");
        assert_eq!(fs::read(output).unwrap(), vector());
    }
}

#[test]
fn larger_json_budget_cannot_widen_wire_scalar_or_depth_limits() {
    let options = compiler::CompileOptions::new(u64::MAX).unwrap();
    let mut cert = certificate();
    let End::Return { map, .. } = &mut cert.blocks[0].end else { panic!() };
    map[0].constant = Q::from_integer(BigInt::from(1_u8) << (codec::MAX_INTEGER_BYTES * 8));
    let error = api::compile_certificate_json_with_options(&serde_json::to_string(&cert).unwrap(), &options).unwrap_err();
    assert_eq!(error.status(), api::Status::ResourceLimit);
    assert!(error.message().contains("rational magnitude limit"));

    let mut cert = certificate();
    let mut block = cert.blocks[0].clone();
    for _ in 0..codec::MAX_DEPTH {
        block = Block { steps: vec![], end: End::Split {
            expression: kernel_core::model::Expr::zero(), integer: None,
            left: Box::new(block), right: Box::new(cert.blocks[0].clone()) } };
    }
    cert.blocks[0] = block;
    let error = api::compile_certificate_json_with_options(&serde_json::to_string(&cert).unwrap(), &options).unwrap_err();
    assert_eq!(error.status(), api::Status::ResourceLimit);
    assert!(error.message().contains("block depth limit"));
}
