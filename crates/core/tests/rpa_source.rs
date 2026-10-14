use kernel_core::{
    codec, lp,
    proof::*,
    rpa, rpa_source,
    verify::{Limits, verify_request},
};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    sync::atomic::{AtomicUsize, Ordering},
};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn json_certificate(path: &str) -> Certificate {
    rpa::assemble(&fs::read_to_string(root().join(path)).unwrap()).unwrap()
}
fn assert_round_trip(certificate: &Certificate) -> String {
    let source = rpa_source::disassemble(certificate).unwrap();
    let recovered =
        rpa_source::assemble(&source).unwrap_or_else(|error| panic!("{error}\n{source}"));
    assert_eq!(&recovered, certificate);
    assert_eq!(
        codec::encode_certificate(&recovered).unwrap(),
        codec::encode_certificate(certificate).unwrap()
    );
    assert_eq!(source, rpa_source::disassemble(&recovered).unwrap());
    source
}

#[test]
fn documented_source_examples_are_the_same_verified_proofs() {
    for name in ["redundant", "elimination", "piecewise"] {
        let directory = root().join("docs/rpx/examples").join(name);
        let original =
            rpa::assemble(&fs::read_to_string(directory.join("proof.rpa")).unwrap()).unwrap();
        let source =
            lp::parse_lp(&fs::read_to_string(directory.join("source.lp")).unwrap()).unwrap();
        let target =
            lp::parse_lp(&fs::read_to_string(directory.join("target.lp")).unwrap()).unwrap();
        let readable = rpa_source::assemble_with_models(
            &fs::read_to_string(directory.join("proof.rpas")).unwrap(),
            &source,
            &target,
        )
        .unwrap();
        assert_eq!(readable, original, "{name}");
        let request =
            rpa::parse_request(&fs::read_to_string(directory.join("request.json")).unwrap())
                .unwrap();
        verify_request(&source, &target, &readable, &request, &Limits::default()).unwrap();
        assert_round_trip(&original);
        let mut bad = readable.clone();
        // Readability conveniences never discharge a missing proof obligation.
        fn remove_check(block: &mut Block) {
            match &mut block.end {
                End::Return { checks, .. } => {
                    checks.pop();
                }
                End::Split { left, .. } => remove_check(left),
                _ => panic!("unexpected manual example"),
            }
        }
        remove_check(&mut bad.blocks[0]);
        let unchecked = rpa_source::assemble(&rpa_source::disassemble(&bad).unwrap()).unwrap();
        assert!(
            verify_request(&source, &target, &unchecked, &request, &Limits::default()).is_err()
        );
    }
}

#[test]
fn existing_lifts_domains_and_v10_vectors_round_trip() {
    for path in [
        "bench/theorem-generated/flow-1/proof.rpa",
        "bench/theorem-generated/interval-1/proof.rpa",
        "bench/theorem-generated/menu-1-k2/proof.rpa",
        "bench/theorem-generated/injectivity-1/proof.rpa",
        "bench/signed-generated/signed-1-c2_7-s812/proof.rpa",
        "tests/vectors/conditional-halfspace.rpa",
        "tests/vectors/conditional-level-halfspace.rpa",
        "tests/vectors/conditional-old-none.rpa",
        "tests/vectors/contract-v10.rpa",
    ] {
        assert_round_trip(&json_certificate(path));
    }
}

#[test]
fn all_existing_record_variants_and_scalar_positions_have_readable_forms() {
    let expr = json!({"constant":"1/3", "terms":[[0,"-2/7"],[1,"1"]]});
    let leaf = json!({"steps":[], "end":{"Return":{"map":[expr.clone()], "checks":["Exact"]}}});
    let refs = json!([{"VarLower":0},{"VarUpper":1},{"VarInt":2},{"RowLower":3},{"RowUpper":4},{"RowEq":5},{"Local":6},{"Assumption":7},"Exact"]);
    let steps = json!([
        {"Lin":{"id":0,"kind":"Eq","constant":"-1/2","terms":[[{"RowEq":0},"-1"],[{"RowEq":0},"0"],["Exact","2/3"]]}},
        {"Lin":{"id":1,"kind":"Le","constant":"0","terms":[]}},
        {"Lin":{"id":2,"kind":"Int","constant":"0","terms":[[{"VarInt":0},"1"]]}},
        {"Round":{"id":3,"le":{"Local":1},"integer":{"Local":2}}},
        {"Drop":{"ids":[1,2]}},
        {"Drop":{"ids":[]}},
        {"EqPair":{"id":4,"positive":{"VarUpper":0},"negative":{"VarLower":0}}},
        {"Cases":{"id":5,"kind":"Le","expression":expr.clone(),"split":expr.clone(),"integer":null,
            "left":{"steps":[],"end":{"Witness":{"Assumption":0}}},
            "right":{"steps":[],"end":{"Absurd":{"Assumption":0}}}}},
        {"Plotkin":{"id":6,"bits":2,"distance":1,"variables":[[0,u64::MAX]],"cliques":["Exact"]}}
    ]);
    let flow = json!({"nodes":2,"arcs":[[0,1]],"groups":[{"source":0,"commodities":[[1,"2/3"]],"flows":[expr.clone()],"nonnegative":["Exact"],"balances":["Exact","Exact"]}]});
    let subflow = json!({"nodes":2,"arcs":[[0,1]],"groups":[{"source":0,"demands":[[1,"2/3"]],"flows":[expr.clone()],"nonnegative":["Exact"],"balances":["Exact","Exact"]}]});
    let ends = vec![
        json!({"Return":{"map":[expr.clone()],"checks":refs.clone()}}),
        json!({"Split":{"expression":expr.clone(),"integer":{"VarInt":0},"left":leaf.clone(),"right":leaf.clone()}}),
        json!({"Absurd":{"fact":{"Local":0}}}),
        json!({"FlowLift":{"witness":flow,"body":leaf.clone()}}),
        json!({"IntervalLift":{"intervals":[{"lower":[expr.clone()],"upper":[expr.clone()],"checks":["Exact"]}],"body":leaf.clone()}}),
        json!({"MenuLift":{"menus":[{"maximum_index":2,"activation":expr.clone(),"index":expr.clone(),"checks":refs.clone()}],"body":leaf.clone()}}),
        json!({"SignedLift":{"decompositions":[{"capacity":"5/3","flow":expr.clone(),"activation":expr.clone(),"checks":refs.clone()}],"body":leaf.clone()}}),
        json!({"SubflowLift":{"witness":subflow,"body":leaf.clone()}}),
        json!({"ImproveReturn":{"map":[expr.clone()],"checks":refs.clone(),"margin":{"Constant":"1/2"}}}),
        json!({"ImproveReturn":{"map":[expr.clone()],"checks":refs.clone(),"margin":{"Predicate":"1/3"}}}),
        json!({"PositiveRefutation":{"fact":{"Assumption":0}}}),
    ];
    let claim = json!({"reverse":false,"input_integers":true,"output_integers":true,"objective":"NonIncreasing","projection":[[0,1]],"inverse":null,
        "input_objective_lower":"-1/3","affine_projection":[[expr.clone(),expr.clone()]],"input_objective_level":"2/3","input_halfspace":expr.clone()});
    let blocks: Vec<Value> = ends
        .into_iter()
        .map(|end| json!({"steps":steps.clone(),"end":end}))
        .collect();
    let certificate: Certificate = serde_json::from_value(json!({
        "claims":vec![claim;blocks.len()],"blocks":blocks,
        "points":[
            {"claim":{"Feasible":{"target":false,"integers":true,"objective":"1/3"}},"values":["1/3"]},
            {"claim":{"Strictness":{"inclusion_claim":0}},"values":["1/3"]},
            {"claim":{"FiberStrictness":{"inclusion_claim":0}},"values":["1/3"],"refutation":leaf.clone()},
            {"claim":{"ImageExclusion":{"point_in_target":true,"map":[expr.clone()]}},"values":["1/3"]}
        ],
        "bijections":[{"claim":{"forward_claim":0,"reverse_claim":1},"injectivity":{"steps":steps,"checks":refs}}],
        "improvements":[{"claim":{"target":false,"integers":true,"positive":expr},"block":leaf}]
    })).unwrap();
    assert_eq!(codec::certificate_version(&certificate).unwrap(), 10);
    let source = assert_round_trip(&certificate);
    assert!(source.contains("SubflowLift"));
    assert!(source.contains("lin.eq"));
    assert!(source.contains("18446744073709551615"));
}

const NAMED_SOURCE: &str = "RPA-S 1\n\
// Coordinates and proof references have explicit numeric bindings.\n\
let retained = x0;\n\
let lower_bound = lower(retained);\n\
let derived = f0;\n\
certificate {\n\
  claims: [{reverse:false, input_integers:false, output_integers:false, objective:Equal, projection:[], inverse:null}],\n\
  blocks: [{steps:[lin.le(derived, lower_bound)], end:Return {map:[expr(retained)], checks:[derived, exact]}}]\n\
}\n";

#[test]
fn aliases_comments_and_exact_affine_arithmetic_lower_deterministically() {
    let certificate = rpa_source::assemble(NAMED_SOURCE).unwrap();
    assert_eq!(
        certificate.blocks[0].steps,
        vec![Step::Lin {
            id: 0,
            kind: Kind::Le,
            constant: kernel_core::model::parse_q("0").unwrap(),
            terms: vec![(Ref::VarLower(0), kernel_core::model::parse_q("1").unwrap())],
        }]
    );
    let arithmetic = NAMED_SOURCE.replace(
        "expr(retained)",
        "expr(1/3 + (2 * retained - retained) / 2 - 0.1)",
    );
    let parsed = rpa_source::assemble(&arithmetic).unwrap();
    let End::Return { map, .. } = &parsed.blocks[0].end else {
        panic!()
    };
    assert_eq!(
        map[0].constant,
        kernel_core::model::parse_q("7/30").unwrap()
    );
    assert_eq!(
        map[0].terms,
        vec![(0, kernel_core::model::parse_q("1/2").unwrap())]
    );
    assert_round_trip(&parsed);
}

#[test]
fn arithmetic_precedence_groups_and_signs_match_exact_rational_results() {
    use kernel_core::model::{Expr, Q};
    for seed in 0i64..64 {
        let a = seed % 9 - 4;
        let b = seed % 7 - 3;
        let c = seed % 5 - 2;
        let d = seed % 11 - 5;
        let denominator = seed % 6 + 1;
        let factor = seed % 4 - 2;
        let math = format!("expr(({a}*x0 + {b})/{denominator} - ({c}*x0 - {d})*{factor})");
        let certificate =
            rpa_source::assemble(&NAMED_SOURCE.replace("expr(retained)", &math)).unwrap();
        let End::Return { map, .. } = &certificate.blocks[0].end else {
            panic!()
        };
        let constant = Q::new(b.into(), denominator.into()) + Q::from_integer((d * factor).into());
        let coefficient =
            Q::new(a.into(), denominator.into()) - Q::from_integer((c * factor).into());
        let terms = if coefficient == Q::from_integer(0.into()) {
            vec![]
        } else {
            vec![(0, coefficient)]
        };
        assert_eq!(map[0], Expr { constant, terms }, "{math}");
    }
}

#[test]
fn structural_splices_expand_full_witnesses_in_order() {
    let source = "RPA-S 1\ncertificate {claims:[{reverse:false,input_integers:false,output_integers:false,objective:None,projection:[pairs(2,5,3)],inverse:null}],blocks:[{steps:[],end:Return {map:[identity(2,3),repeat(2,expr(1))],checks:[repeat(5,exact)]}}]}";
    let certificate = rpa_source::assemble(source).unwrap();
    assert_eq!(
        certificate.claims[0].projection,
        vec![(2, 5), (3, 6), (4, 7)]
    );
    let End::Return { map, checks } = &certificate.blocks[0].end else {
        panic!()
    };
    assert_eq!(map.len(), 5);
    assert_eq!(
        map[..3],
        [
            kernel_core::model::Expr::var(2),
            kernel_core::model::Expr::var(3),
            kernel_core::model::Expr::var(4)
        ]
    );
    assert_eq!(checks, &vec![Ref::Exact; 5]);
    assert_round_trip(&certificate);
}

#[test]
fn long_linear_combinations_do_not_recharge_unchanged_prefixes() {
    let terms = vec!["exact"; 50_000].join(" + ");
    let source = NAMED_SOURCE.replace(
        "lin.le(derived, lower_bound)",
        &format!("lin.le(derived, {terms})"),
    );
    let certificate = rpa_source::assemble(&source).unwrap();
    let Step::Lin { terms, .. } = &certificate.blocks[0].steps[0] else {
        panic!()
    };
    assert_eq!(terms.len(), 50_000);
    assert!(
        terms
            .iter()
            .all(|(reference, coefficient)| reference == &Ref::Exact
                && coefficient == &kernel_core::model::parse_q("1").unwrap())
    );
}

#[test]
fn malformed_and_ambiguous_source_is_rejected_with_locations() {
    for source in [
        NAMED_SOURCE.replace("let retained = x0;", "let retained = unknown;"),
        NAMED_SOURCE.replace(
            "let retained = x0;",
            "let retained = x0; let retained = x1;",
        ),
        NAMED_SOURCE.replace("reverse:false", "reverse:false,reverse:true"),
        NAMED_SOURCE.replace("objective:Equal", "objective:Equal,unexpected:true"),
        NAMED_SOURCE.replace("expr(retained)", "expr(x0 * x1)"),
        NAMED_SOURCE.replace("expr(retained)", "expr(1 / 0)"),
        NAMED_SOURCE.replace("x0;", "x4294967296;"),
        NAMED_SOURCE.replace("lower(retained)", "lower(q(1))"),
        format!("{NAMED_SOURCE} trailing"),
        format!("{NAMED_SOURCE} /* unclosed"),
        NAMED_SOURCE.replace(
            "lin.le(derived, lower_bound)",
            "lin.le(derived, lower_bound * lower_bound)",
        ),
    ] {
        let error = rpa_source::assemble(&source).unwrap_err();
        assert!(error.starts_with("INVALID"), "{error}");
        assert!(
            error.contains("line ") || error.contains("schema:"),
            "{error}"
        );
    }
    for source in [
        NAMED_SOURCE.replace("RPA-S 1\n", "RPA-S 1\r\n"),
        NAMED_SOURCE.replace("RPA-S 1", "RPA-S 2"),
    ] {
        assert!(
            rpa_source::assemble(&source)
                .unwrap_err()
                .starts_with("INVALID")
        );
    }
    // New syntax does not alter the frozen JSON parser's acceptance language.
    assert!(
        rpa::assemble(NAMED_SOURCE)
            .unwrap_err()
            .starts_with("INVALID")
    );
}

#[test]
fn expansion_and_source_depth_are_bounded_before_allocation() {
    let huge = format!(
        "RPA-S 1\ncertificate {{ claims:[], blocks:[], points:[repeat({},null)] }}",
        rpa_source::MAX_EXPANDED_NODES + 1
    );
    assert!(
        rpa_source::assemble(&huge)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
    let overflow = "RPA-S 1\ncertificate {claims:[],blocks:[range(4294967295,2)]}";
    assert!(
        rpa_source::assemble(overflow)
            .unwrap_err()
            .starts_with("INVALID")
    );
    let deep = format!(
        "RPA-S 1\ncertificate {{claims:[],blocks:[] ,points:{}0{} }}",
        "[".repeat(140),
        "]".repeat(140)
    );
    assert!(
        rpa_source::assemble(&deep)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
    let huge_bytes = format!(
        "RPA-S 1\nlet payload = \"{}\"; certificate {{claims:[],blocks:[],points:[repeat(100000,payload)]}}",
        "a".repeat(10_000)
    );
    assert!(
        rpa_source::assemble(&huge_bytes)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
    let unary = NAMED_SOURCE.replace(
        "expr(retained)",
        &format!("expr({}retained)", "-".repeat(140)),
    );
    assert!(
        rpa_source::assemble(&unary)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
}

#[test]
fn inherited_scalar_text_limits_have_resource_outcomes() {
    let oversized_literal =
        NAMED_SOURCE.replace("expr(retained)", &format!("expr({})", "9".repeat(4100)));
    assert!(
        rpa_source::assemble(&oversized_literal)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
    let mut certificate = json_certificate("tests/vectors/contract-v10.rpa");
    let large = kernel_core::model::Q::from_integer(num_bigint::BigInt::from(1u8) << 14_000usize);
    assert!(kernel_core::model::check_q(&large).is_ok());
    certificate.points[0].values[0] = large;
    assert!(
        codec::encode_certificate(&certificate)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
    assert!(
        rpa_source::disassemble(&certificate)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
}

static NEXT: AtomicUsize = AtomicUsize::new(0);
struct Temporary(PathBuf);
impl Temporary {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "rpx-readable-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
    fn path(&self, name: &str) -> PathBuf {
        self.0.join(name)
    }
}
impl Drop for Temporary {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn run_cli(command: &str, input: &Path, output: &Path) -> Value {
    let result = Command::new(env!("CARGO_BIN_EXE_rpx"))
        .arg(command)
        .arg(input)
        .arg(output)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stdout)
    );
    serde_json::from_slice(&result.stdout).unwrap()
}

#[test]
fn cli_accepts_both_formats_and_exposes_readable_disassembly() {
    let temporary = Temporary::new();
    let original = root().join("docs/rpx/examples/elimination/proof.rpa");
    let source = root().join("docs/rpx/examples/elimination/proof.rpas");
    assert_eq!(
        run_cli("assemble", &original, &temporary.path("original.rpx"))["status"],
        "ASSEMBLED"
    );
    assert_eq!(
        run_cli("assemble", &source, &temporary.path("source.rpx"))["status"],
        "ASSEMBLED"
    );
    assert_eq!(
        fs::read(temporary.path("source.rpx")).unwrap(),
        fs::read(temporary.path("original.rpx")).unwrap()
    );
    assert_eq!(
        run_cli(
            "disassemble-source",
            &temporary.path("source.rpx"),
            &temporary.path("recovered.rpas")
        )["status"],
        "DISASSEMBLED"
    );
    assert!(
        fs::read_to_string(temporary.path("recovered.rpas"))
            .unwrap()
            .starts_with(rpa_source::HEADER)
    );
    run_cli(
        "assemble",
        &temporary.path("recovered.rpas"),
        &temporary.path("recovered.rpx"),
    );
    assert_eq!(
        fs::read(temporary.path("recovered.rpx")).unwrap(),
        fs::read(temporary.path("original.rpx")).unwrap()
    );
    run_cli(
        "disassemble",
        &temporary.path("source.rpx"),
        &temporary.path("legacy.rpa"),
    );
    assert!(
        fs::read_to_string(temporary.path("legacy.rpa"))
            .unwrap()
            .starts_with("RPA 1\n{")
    );
}
