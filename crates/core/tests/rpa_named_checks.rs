use kernel_core::{
    codec, lp,
    model::Model,
    proof::*,
    rpa, rpa_source,
    verify::{Limits, verify_request},
};
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    sync::atomic::{AtomicUsize, Ordering},
};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn example(name: &str) -> (String, Model, Model, Certificate) {
    let dir = root().join("docs/rpx/examples").join(name);
    let source = lp::parse_lp(&fs::read_to_string(dir.join("source.lp")).unwrap()).unwrap();
    let target = lp::parse_lp(&fs::read_to_string(dir.join("target.lp")).unwrap()).unwrap();
    let cert = rpa::assemble(&fs::read_to_string(dir.join("proof.rpa")).unwrap()).unwrap();
    (
        fs::read_to_string(dir.join("proof.rpas")).unwrap(),
        source,
        target,
        cert,
    )
}

#[test]
fn named_checks_bind_to_model_names_in_any_order() {
    let (text, source, target, expected) = example("elimination");
    let shuffled = text.replace(
        "          variable[\"y\"].lower: lower(x1), // Target y >= 0\n          variable[\"y\"].upper: upper(x1), // Target y <= 1",
        "          variable[\"y\"].upper: upper(x1), // Target y <= 1\n          variable[\"y\"].lower: lower(x1), // Target y >= 0");
    assert_ne!(shuffled, text);
    assert_eq!(
        rpa_source::assemble_with_models(&shuffled, &source, &target).unwrap(),
        expected
    );
    let numeric = shuffled
        .replace("variable[\"y\"]", "variable[0]")
        .replace("variable[\"x0\"]", "variable[0]")
        .replace("variable[\"x1\"]", "variable[1]")
        .replace("row[\"balance\"]", "row[0]")
        .replace("inverse.coordinate[\"x0\"]", "inverse.coordinate[0]")
        .replace("inverse.coordinate[\"x1\"]", "inverse.coordinate[1]")
        .replace("inverse.coordinate[\"y\"]", "inverse.coordinate[0]");
    assert_eq!(
        rpa_source::assemble_with_models(&numeric, &source, &target).unwrap(),
        expected
    );
    let parsed = rpa_source::parse(&text).unwrap();
    assert_eq!(parsed.declared_models().unwrap().source, "source.lp");
    assert!(
        parsed
            .assemble()
            .unwrap_err()
            .contains("require actual source and target models")
    );
}

#[test]
fn missing_duplicate_wrong_kind_and_out_of_range_obligations_are_rejected() {
    let (text, source, target, _) = example("elimination");
    for (changed, message) in [
        (
            text.replace(
                "          objective.equal: f0,        // 目标差 (1 - x1) - x0 = 0\n",
                "",
            ),
            "missing obligation objective.equal",
        ),
        (
            text.replacen(
                "variable[\"y\"].lower: lower(x1),",
                "variable[\"y\"].lower: lower(x1), variable[0].lower: lower(x1),",
                1,
            ),
            "duplicate obligation variable[0].lower",
        ),
        (
            text.replacen("objective.equal:", "objective.non_increasing:", 1),
            "unknown or inapplicable obligation objective.non_increasing",
        ),
        (
            text.replacen("variable[\"y\"].upper:", "variable[\"y\"].integer:", 1),
            "unknown or inapplicable obligation variable[\"y\"].integer",
        ),
        (
            text.replacen("row[\"balance\"].equal:", "row[\"balance\"].upper:", 1),
            "unknown or inapplicable obligation row[\"balance\"].upper",
        ),
        (
            text.replacen("variable[\"y\"].lower", "variable[1].lower", 1),
            "unknown or inapplicable obligation variable[1].lower",
        ),
        (
            text.replacen("variable[\"y\"].lower", "variable[\"typo\"].lower", 1),
            "unknown or inapplicable obligation variable[\"typo\"].lower",
        ),
        (
            text.replacen("projection[0]", "projection[1]", 1),
            "unknown or inapplicable obligation projection[1]",
        ),
    ] {
        assert_ne!(changed, text);
        let error = rpa_source::assemble_with_models(&changed, &source, &target).unwrap_err();
        assert!(error.starts_with("INVALID"), "{error}");
        assert!(error.contains(message), "{error}");
    }
    let duplicate = text.replacen(
        "objective.equal: f0,",
        "objective.equal: f0, objective.equal: exact,",
        1,
    );
    assert!(
        rpa_source::assemble_with_models(&duplicate, &source, &target)
            .unwrap_err()
            .contains("duplicate field")
    );
    let wrong_model =
        lp::parse_lp("Minimize\nobj: 1 - y\nSubject To\nBounds\ny free\nEnd\n").unwrap();
    assert!(
        rpa_source::assemble_with_models(&text, &source, &wrong_model)
            .unwrap_err()
            .contains("inapplicable obligation variable[\"y\"]")
    );
}

#[test]
fn obligation_names_do_not_replace_mathematical_evidence() {
    let (text, source, target, expected) = example("elimination");
    let bad = text.replacen("objective.equal: f0,", "objective.equal: exact,", 1);
    let certificate = rpa_source::assemble_with_models(&bad, &source, &target).unwrap();
    let request = Request {
        claims: expected.claims,
        ..Request::default()
    };
    assert!(verify_request(&source, &target, &certificate, &request, &Limits::default()).is_err());
}

#[test]
fn all_documented_branches_round_trip_with_named_checks() {
    for name in ["elimination", "redundant", "piecewise"] {
        let (_, source, target, certificate) = example(name);
        let text = rpa_source::disassemble_with_models(&certificate, &source, &target).unwrap();
        assert!(text.contains("checks {"));
        assert!(text.contains("objective.equal:"));
        assert_eq!(
            rpa_source::assemble_with_models(&text, &source, &target).unwrap(),
            certificate
        );
    }
}

#[test]
fn lift_injectivity_integer_and_v10_improvement_checks_keep_frozen_order() {
    for directory in [
        "bench/theorem-generated/flow-1",
        "bench/theorem-generated/interval-1",
        "bench/theorem-generated/menu-1-k2",
        "bench/theorem-generated/injectivity-1",
        "bench/signed-generated/signed-1-c2_7-s812",
        "cases/test86",
    ] {
        let dir = root().join(directory);
        let source = codec::decode_model(&fs::read(dir.join("source.mcm")).unwrap()).unwrap();
        let target = codec::decode_model(&fs::read(dir.join("target.mcm")).unwrap()).unwrap();
        let certificate =
            rpa::assemble(&fs::read_to_string(dir.join("proof.rpa")).unwrap()).unwrap();
        let request =
            rpa::parse_request(&fs::read_to_string(dir.join("request.json")).unwrap()).unwrap();
        let named = rpa_source::disassemble_with_models(&certificate, &source, &target).unwrap();
        let recovered = rpa_source::assemble_with_models(&named, &source, &target).unwrap();
        assert_eq!(recovered, certificate, "{directory}");
        assert_eq!(
            codec::encode_certificate(&recovered).unwrap(),
            codec::encode_certificate(&certificate).unwrap()
        );
        verify_request(&source, &target, &recovered, &request, &Limits::default()).unwrap();
        if directory.ends_with("injectivity-1") {
            assert!(named.contains("injectivity.coordinate["));
            assert!(named.contains("bijection[0].coordinate["));
        }
    }
    let dir = root().join("tests/vectors");
    let source =
        codec::decode_model(&fs::read(dir.join("contract-v10-source.mcm")).unwrap()).unwrap();
    let target =
        codec::decode_model(&fs::read(dir.join("contract-v10-target.mcm")).unwrap()).unwrap();
    let certificate =
        rpa::assemble(&fs::read_to_string(dir.join("contract-v10.rpa")).unwrap()).unwrap();
    let named = rpa_source::disassemble_with_models(&certificate, &source, &target).unwrap();
    assert!(named.contains("objective.improve:"));
    assert_eq!(
        rpa_source::assemble_with_models(&named, &source, &target).unwrap(),
        certificate
    );
}

#[test]
fn scalar_errors_and_model_declarations_keep_strict_classification() {
    let (text, source, target, _) = example("elimination");
    for modified in [
        text.replace("models { source:", "models { unknown: \"bad\", source:"),
        text.replace(
            "models { source: \"source.lp\", target: \"target.lp\" }",
            "models { source: \"source.lp\" }",
        ),
        text.replace(
            "models { source: \"source.lp\", target: \"target.lp\" }",
            "models { source: \"source.lp\", target: \"target.lp\" } models {}",
        ),
    ] {
        assert!(
            rpa_source::assemble_with_models(&modified, &source, &target)
                .unwrap_err()
                .starts_with("INVALID")
        );
    }
    let scalar = text.replacen(
        "objective: Equal,",
        &format!(
            "objective: Equal, input_objective_lower: \"{}\",",
            "9".repeat(4100)
        ),
        1,
    );
    assert!(
        rpa_source::assemble_with_models(&scalar, &source, &target)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
}

#[test]
fn affine_observations_inverse_levels_and_input_lower_bounds_are_distinct_names() {
    use serde_json::json;
    let source = lp::parse_lp("Minimize\nobj: x\nSubject To\nBounds\n0 <= x <= 0\nEnd\n").unwrap();
    let target = lp::parse_lp("Minimize\nobj: y\nSubject To\nBounds\n0 <= y <= 0\nEnd\n").unwrap();
    let expression = json!({"constant":"0","terms":[[0,"1"]]});
    let forward = json!({"reverse":false,"input_integers":false,"output_integers":false,"objective":"Equal",
        "projection":[[0,0]],"affine_projection":[[expression.clone(),expression.clone()]],"inverse":1,"input_objective_lower":"0"});
    let mut reverse = forward.clone();
    reverse["reverse"] = json!(true);
    reverse["inverse"] = json!(0);
    reverse
        .as_object_mut()
        .unwrap()
        .remove("input_objective_lower");
    reverse["input_objective_level"] = json!("0");
    let certificate: Certificate = serde_json::from_value(json!({"claims":[forward,reverse],"blocks":[
        {"steps":[{"EqPair":{"id":0,"positive":{"VarUpper":0},"negative":{"VarLower":0}}}],
         "end":{"Return":{"map":[expression.clone()],"checks":[{"VarLower":0},{"VarUpper":0},"Exact","Exact","Exact","Exact",{"Local":0},{"VarLower":0}]}}},
        {"steps":[],"end":{"Return":{"map":[expression],"checks":[{"VarLower":0},{"VarUpper":0},"Exact","Exact","Exact","Exact"]}}}
    ]})).unwrap();
    let request = Request {
        claims: certificate.claims.clone(),
        ..Request::default()
    };
    verify_request(&source, &target, &certificate, &request, &Limits::default()).unwrap();
    let named = rpa_source::disassemble_with_models(&certificate, &source, &target).unwrap();
    for key in [
        "affine_projection[0]:",
        "inverse.objective_level:",
        "input.objective_lower:",
    ] {
        assert!(named.contains(key), "{named}");
    }
    assert_eq!(
        rpa_source::assemble_with_models(&named, &source, &target).unwrap(),
        certificate
    );
}

static NEXT: AtomicUsize = AtomicUsize::new(0);
struct Temporary(PathBuf);
impl Temporary {
    fn new() -> Self {
        let dir = std::env::temp_dir().join(format!(
            "rpx-named-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&dir).unwrap();
        Self(dir)
    }
}
impl Drop for Temporary {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn cli_resolves_model_paths_from_source_file_and_emits_reassemblable_bindings() {
    let dir = root().join("docs/rpx/examples/elimination");
    let tmp = Temporary::new();
    let output = tmp.0.join("proof.rpx");
    let result = Command::new(env!("CARGO_BIN_EXE_rpx"))
        .current_dir(&tmp.0)
        .arg("assemble")
        .arg(dir.join("proof.rpas"))
        .arg(&output)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stdout)
    );
    let readable = tmp.0.join("named.rpas");
    let result = Command::new(env!("CARGO_BIN_EXE_rpx"))
        .arg("disassemble-source")
        .arg(&output)
        .arg("--models")
        .arg(dir.join("source.lp"))
        .arg(dir.join("target.lp"))
        .arg(&readable)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stdout)
    );
    let text = fs::read_to_string(&readable).unwrap();
    assert!(text.contains("models {"));
    assert!(text.contains("inverse.coordinate[\"x0\"]:"));
    let recovered = tmp.0.join("recovered.rpx");
    let result = Command::new(env!("CARGO_BIN_EXE_rpx"))
        .current_dir(&tmp.0)
        .arg("assemble")
        .arg(&readable)
        .arg(&recovered)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stdout)
    );
    assert_eq!(fs::read(output).unwrap(), fs::read(recovered).unwrap());
    for operation in ["assemble", "disassemble-source"] {
        for args in [
            vec!["--models"],
            vec!["--models", "a"],
            vec!["--models", "a", "b"],
            vec!["--models", "a", "b", "input"],
            vec!["input", "output", "--models", "a"],
            vec![
                "input", "output", "--models", "a", "b", "--models", "a", "b",
            ],
        ] {
            let result = Command::new(env!("CARGO_BIN_EXE_rpx"))
                .arg(operation)
                .args(args)
                .output()
                .unwrap();
            assert_eq!(result.status.code(), Some(2));
            let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
            assert_eq!(report["status"], "INVALID");
            assert!(
                report["message"]
                    .as_str()
                    .unwrap()
                    .starts_with("INVALID usage")
            );
        }
    }
}
