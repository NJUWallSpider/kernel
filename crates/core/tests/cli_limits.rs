use kernel_core::{codec, model::{Expr, Model, Q, Var}, proof::*, verify::{verify_request, Limits}};
use serde_json::{json, Value};
use std::{fs, path::PathBuf, process::Command, sync::atomic::{AtomicUsize, Ordering}};

static NEXT_FIXTURE: AtomicUsize = AtomicUsize::new(0);

struct Fixture { dir: PathBuf, work: u64 }
impl Fixture {
    fn new() -> Self {
        let dir = std::env::temp_dir().join(format!("rpx-cli-limits-{}-{}", std::process::id(), NEXT_FIXTURE.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir(&dir).unwrap();
        let zero = Q::from_integer(0.into());
        let model = Model { name: "tiny".into(), vars: vec![Var { name: "x".into(), integer: false, lower: Some(zero.clone()), upper: None }], rows: vec![], objective: Expr::zero() };
        let claim = Claim { input_halfspace:None,input_objective_level:None, affine_projection: vec![], input_objective_lower: None, reverse: false, input_integers: false, output_integers: false, objective: Objective::Equal, projection: vec![], inverse: None };
        let cert = Certificate { improvements:vec![], bijections: vec![], points: vec![], claims: vec![claim.clone()], blocks: vec![Block { steps: vec![Step::Lin { id: 0, kind: Kind::Le, constant: zero, terms: vec![(Ref::VarLower(0), Q::from_integer(1.into()))] }], end: End::Return { map: vec![Expr::var(0)], checks: vec![Ref::Local(0), Ref::Exact] } }] };
        let request = Request { improvements:vec![], claims: vec![claim], points: vec![], bijections: vec![] };
        let stats = verify_request(&model, &model, &cert, &request, &Limits::default()).unwrap();
        // The former work policy accepts this same proof with identical work accounting.
        let old = verify_request(&model, &model, &cert, &request, &Limits { work: 100_000_000, ..Limits::default() }).unwrap();
        assert_eq!(stats.work, old.work);
        assert!(stats.work > 0);
        let encoded = codec::encode_model(&model).unwrap();
        fs::write(dir.join("source.mcm"), &encoded).unwrap();
        fs::write(dir.join("target.mcm"), &encoded).unwrap();
        fs::write(dir.join("proof.rpx"), codec::encode_certificate(&cert).unwrap()).unwrap();
        fs::write(dir.join("request.json"), serde_json::to_vec(&request).unwrap()).unwrap();
        Self { dir, work: stats.work }
    }
    fn paths(&self) -> Vec<String> {
        ["source.mcm", "target.mcm", "proof.rpx", "request.json"].iter().map(|name| self.dir.join(name).to_str().unwrap().to_owned()).collect()
    }
    fn run(&self, args: &[String]) -> (i32, Value) {
        let output = Command::new(env!("CARGO_BIN_EXE_rpx")).arg("verify").args(args).output().unwrap();
        assert!(output.stderr.is_empty(), "{}", String::from_utf8_lossy(&output.stderr));
        (output.status.code().unwrap(), serde_json::from_slice(&output.stdout).unwrap())
    }
}
impl Drop for Fixture { fn drop(&mut self) { fs::remove_dir_all(&self.dir).unwrap(); } }

#[test]
fn default_small_proof_and_effective_limits() {
    let fixture = Fixture::new();
    let (code, result) = fixture.run(&fixture.paths());
    assert_eq!(code, 0);
    assert_eq!(result["status"], "VERIFIED");
    // These are resource-policy defaults, not proof semantics.
    assert_eq!(result["limits"], json!({"work": 1_000_000_000u64, "live_facts": 1_000_000, "depth": 64}));
    assert_eq!(result["statistics"]["work"], fixture.work);
}

#[test]
fn flags_anywhere_and_resource_errors_echo_limits() {
    let fixture = Fixture::new();
    let paths = fixture.paths();
    let work = fixture.work.to_string();
    let expected = json!({"work": fixture.work, "live_facts": 1, "depth": 64});
    for args in [
        [vec!["--work".into(), work.clone(), "--live-facts".into(), "1".into()], paths.clone()].concat(),
        [paths.clone(), vec!["--live-facts".into(), "1".into(), "--work".into(), work.clone()]].concat(),
        vec![paths[0].clone(), "--work".into(), work.clone(), paths[1].clone(), "--live-facts".into(), "1".into(), paths[2].clone(), paths[3].clone()],
    ] {
        let (code, result) = fixture.run(&args);
        assert_eq!(code, 0);
        assert_eq!(result["status"], "VERIFIED");
        assert_eq!(result["limits"], expected);
    }
    let maximum = [paths.clone(), vec!["--work".into(), u64::MAX.to_string(), "--live-facts".into(), usize::MAX.to_string()]].concat();
    let (code, result) = fixture.run(&maximum);
    assert_eq!(code, 0);
    assert_eq!(result["limits"], json!({"work": u64::MAX, "live_facts": usize::MAX, "depth": 64}));
    for (flag, value, expected) in [
        ("--work", (fixture.work - 1).to_string(), json!({"work": fixture.work - 1, "live_facts": 1_000_000, "depth": 64})),
        ("--work", "0".into(), json!({"work": 0, "live_facts": 1_000_000, "depth": 64})),
        ("--live-facts", "0".into(), json!({"work": 1_000_000_000u64, "live_facts": 0, "depth": 64})),
    ] {
        let args = [paths.clone(), vec![flag.into(), value]].concat();
        let (code, result) = fixture.run(&args);
        assert_eq!(code, 3);
        assert_eq!(result["status"], "RESOURCE_LIMIT");
        assert_eq!(result["limits"], expected);
    }
    fs::write(fixture.dir.join("request.json"), b"[]").unwrap();
    let (code, result) = fixture.run(&[paths, vec!["--work".into(), work]].concat());
    assert_eq!(code, 2);
    assert_eq!(result["status"], "INVALID");
    assert_eq!(result["limits"], json!({"work": fixture.work, "live_facts": 1_000_000, "depth": 64}));
}

#[test]
fn malformed_flags_use_invalid_usage() {
    let fixture = Fixture::new();
    let paths = fixture.paths();
    for flag in ["--work", "--live-facts"] {
        for value in ["no", "1.5", "-1", "18446744073709551616"] {
            let (code, result) = fixture.run(&[paths.clone(), vec![flag.into(), value.into()]].concat());
            assert_eq!(code, 2);
            assert_eq!(result["status"], "INVALID");
            assert!(result["message"].as_str().unwrap().starts_with("INVALID usage:"));
        }
        let (code, result) = fixture.run(&[paths.clone(), vec![flag.into()]].concat());
        assert_eq!(code, 2);
        assert_eq!(result["status"], "INVALID");
    }
    for args in [
        vec![], paths[..3].to_vec(), [paths.clone(), vec!["extra".into()]].concat(),
        [paths.clone(), vec!["--depth".into(), "64".into()]].concat(),
    ] {
        let (code, result) = fixture.run(&args);
        assert_eq!(code, 2);
        assert_eq!(result["status"], "INVALID");
        assert!(result["message"].as_str().unwrap().starts_with("INVALID usage:"));
    }
}

#[test]
fn facade_matches_cli_and_classifies_status() {
    use kernel_core::api::{self, Status};
    let fixture = Fixture::new();
    let paths = fixture.paths();
    let source = fs::read(&paths[0]).unwrap();
    let target = fs::read(&paths[1]).unwrap();
    let proof = fs::read(&paths[2]).unwrap();
    let request = fs::read_to_string(&paths[3]).unwrap();

    // In-process verification reports the same contract, limits and work as the
    // CLI, and omits the read phase it never had.
    let report = api::verify_bytes(&source, &target, &proof, &request, &Limits::default()).unwrap();
    assert_eq!(report["status"], "VERIFIED");
    assert_eq!(report["statistics"]["work"], fixture.work);
    assert_eq!(report["limits"], json!({"work": 1_000_000_000u64, "live_facts": 1_000_000, "depth": 64}));
    assert!(report.get("read_us").is_none());

    // Failures carry their category instead of a caller-side prefix guess.
    let error = api::verify_bytes(&source, &target, &proof, "[]", &Limits::default()).unwrap_err();
    assert_eq!(error.status(), Status::Invalid);
    assert_eq!(error.status().exit_code(), 2);
    assert_eq!(error.to_json()["status"], "INVALID");
    assert!(error.to_json().get("limits").is_none(), "limits are echoed only once the caller parsed them");
}

#[test]
fn failure_codes_and_model_export_are_machine_readable() {
    use kernel_core::api::{self, Status};
    let fixture = Fixture::new();
    let paths = fixture.paths();
    let original_request = fs::read(&paths[3]).unwrap();

    // An input rejection that never enters the proof walk carries a code, the
    // status category and no location.
    fs::write(fixture.dir.join("request.json"), b"[]").unwrap();
    let (code, result) = fixture.run(&paths);
    assert_eq!(code, 2);
    assert_eq!(result["status"], "INVALID");
    assert_eq!(result["code"], "empty_request");
    assert!(result.get("location").is_none(), "no walk position exists for an empty request");

    let error = api::verify_bytes(
        &fs::read(&paths[0]).unwrap(),
        &fs::read(&paths[1]).unwrap(),
        &fs::read(&paths[2]).unwrap(),
        "[]",
        &Limits::default(),
    )
    .unwrap_err();
    assert_eq!(error.status(), Status::Invalid);
    assert_eq!(error.code(), "empty_request");
    assert!(error.location().is_none());

    // A caller contract the certificate does not repeat is classified separately.
    let mut request: Value = serde_json::from_slice(&original_request).unwrap();
    request["claims"][0]["objective"] = json!("NonIncreasing");
    let mismatch = request.to_string();
    fs::write(fixture.dir.join("request.json"), &mismatch).unwrap();
    let (code, result) = fixture.run(&paths);
    assert_eq!(code, 2);
    assert_eq!(result["code"], "requested_contract_mismatch");

    // export-model emits the canonical model: string scalars, null unbounded side.
    let out = fixture.dir.join("model.json");
    let output = Command::new(env!("CARGO_BIN_EXE_rpx"))
        .args(["export-model", &paths[0], out.to_str().unwrap()])
        .output()
        .unwrap();
    assert!(output.stderr.is_empty(), "{}", String::from_utf8_lossy(&output.stderr));
    assert_eq!(output.status.code().unwrap(), 0);
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["status"], "EXPORTED");
    assert_eq!(report["variables"], 1);
    assert_eq!(report["rows"], 0);
    let model: Value = serde_json::from_slice(&fs::read(&out).unwrap()).unwrap();
    assert_eq!(model["variables"][0]["lower"], "0");
    assert_eq!(model["variables"][0]["upper"], Value::Null);
    assert_eq!(model["variables"][0]["name"], "x");
    assert_eq!(model["objective"], json!({"constant": "0", "terms": []}));
}
