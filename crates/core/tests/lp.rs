use kernel_core::lp::parse_lp;
use kernel_core::model::{parse_q, Expr, Model, Row, Var, Q};
use num_bigint::BigInt;
use num_traits::{One, Zero};

fn q(s: &str) -> Q {
    parse_q(s).unwrap()
}
fn lp(objective: &str, rows: &str, rest: &str) -> String {
    format!("Minimize\n obj: {objective}\nSubject To\n{rows}{rest}End\n")
}

#[test]
fn affine_terms_constants_and_exact_maximization() {
    let source="MAXIMIZE\n obj: + 0 z - 1/3 x + 0.1 y + 9007199254740993\nSubject To\n c: x + 1 <= y + 3\nEnd\n";
    let m = parse_lp(source).unwrap();
    assert_eq!(
        m.vars.iter().map(|v| v.name.as_str()).collect::<Vec<_>>(),
        vec!["z", "x", "y"]
    );
    assert_eq!(m.objective.constant, q("-9007199254740993"));
    assert_eq!(m.objective.terms, vec![(1, q("1/3")), (2, q("-1/10"))]);
    assert_eq!(m.rows[0].expr.terms, vec![(1, q("1")), (2, q("-1"))]);
    assert_eq!(m.rows[0].upper, Some(q("2")));
    assert_eq!(m.rows[0].expr.constant, Q::zero());
}

#[test]
fn ranges_and_zero_declarations_preserve_order() {
    let m = parse_lp(&lp(
        "0 z + x",
        " r: 1 <= 0 w + y + 2 <= 3\n s: 9 >= x - 2 >= 4\n",
        "Bounds\n v free\nGeneral\n h\n",
    ))
    .unwrap();
    assert_eq!(
        m.vars.iter().map(|v| v.name.as_str()).collect::<Vec<_>>(),
        vec!["z", "x", "w", "y", "v", "h"]
    );
    assert_eq!(
        (m.rows[0].lower.clone(), m.rows[0].upper.clone()),
        (Some(q("-1")), Some(q("1")))
    );
    assert_eq!(
        (m.rows[1].lower.clone(), m.rows[1].upper.clone()),
        (Some(q("6")), Some(q("11")))
    );
    assert!(m.vars[5].integer);
    assert_eq!(m.vars[5].upper, None);
}

#[test]
fn general_and_binary_bounds_intersections() {
    let m = parse_lp(&lp(
        "x + y + z",
        "",
        "Bounds\n 2 <= x <= 7\n y free\n z <= -1\nBinary\n x y\nGeneral\n z\n",
    ))
    .unwrap();
    assert_eq!(
        (m.vars[0].lower.clone(), m.vars[0].upper.clone()),
        (Some(q("2")), Some(q("1")))
    );
    assert_eq!(
        (m.vars[1].lower.clone(), m.vars[1].upper.clone()),
        (Some(q("0")), Some(q("1")))
    );
    assert_eq!(
        (m.vars[2].lower.clone(), m.vars[2].upper.clone()),
        (Some(q("0")), Some(q("-1")))
    );
    assert!(m.vars.iter().all(|v| v.integer));
}

#[test]
fn signed_scientific_bounds_and_empty_semi() {
    let m = parse_lp(&lp(
        "- .5D+2 x + 1/-2 y + 1.25e-1",
        " c: x-y >= -3\n",
        "Bounds\n -inf <= x <= +infinity\n 2 = y\nGen\n x\nSemi\n",
    ))
    .unwrap();
    assert_eq!(m.objective.terms, vec![(0, q("-50")), (1, q("-1/2"))]);
    assert_eq!(m.objective.constant, q("1/8"));
    assert_eq!(m.vars[0].lower, None);
    assert_eq!(m.vars[0].upper, None);
    assert_eq!(m.vars[1].lower, Some(q("2")));
    assert_eq!(m.vars[1].upper, Some(q("2")));
    for cards in [" inf >= x\n x >= -inf\n", " +inf >= x\n -infinity <= x\n"] {
        let m = parse_lp(&lp("x", "", &format!("Bounds\n{cards}"))).unwrap();
        assert_eq!(m.vars[0].lower, None);
        assert_eq!(m.vars[0].upper, None);
    }
}

#[test]
fn named_multiline_and_single_line_unnamed_rows() {
    let m =
        parse_lp("min\n obj: -1\n x + 2\n y\nst\n a: -2 <=\n x + 3 y + 4\n <= 8\n b: x = y\nend\n")
            .unwrap();
    assert_eq!(m.objective.terms, vec![(0, q("-1")), (1, q("2"))]);
    assert_eq!(
        (m.rows[0].lower.clone(), m.rows[0].upper.clone()),
        (Some(q("-6")), Some(q("4")))
    );
    let m = parse_lp(&lp("x", " x <= 2\n x >= 1\n", "")).unwrap();
    assert_eq!(m.rows.len(), 2);
    assert_eq!(m.rows[0].name, "_lp_row_0");
}

#[test]
fn constant_models_comments_and_case_sensitive_names() {
    let m=parse_lp("\\ comment\nmin\n 7 \\ objective comment\nst\n impossible: 1 <= 0\nend\n\\ trailing comment\n").unwrap();
    assert!(m.vars.is_empty());
    assert_eq!(m.objective.constant, q("7"));
    assert_eq!(m.rows[0].upper, Some(q("-1")));
    let m = parse_lp(&lp("X - x + 0 forgotten", "", "")).unwrap();
    assert_eq!(m.vars.len(), 3);
}

#[test]
fn rejects_unsupported_and_ambiguous_inputs() {
    let cases = [
        lp("e", "", ""),
        lp("e9", "", ""),
        lp("eels", "", ""),
        lp("2x", "", ""),
        lp("x * y", "", ""),
        lp("x^2", "", ""),
        lp("[ x ]", "", ""),
        lp("x y", "", ""),
        lp("x", " a: x < 1\n", ""),
        lp("x", " a: x <= 1\n a: x <= 2\n", ""),
        lp("x", " a: 1 <= x >= 0\n", ""),
        lp("x", " a: x <= inf\n", ""),
        lp("x", "", "Semi\n x\n"),
        lp("x", "", "SOS\n"),
        lp("x", "", "Binary\n x\nGeneral\n x\n"),
        lp("x", "", "Bounds\n x <= 1\n x <= 2\n"),
        lp("x", "", "Bounds\n x free\n x >= 0\n"),
        lp("x", "", "Bounds\n x <= -inf\n"),
        lp("x", "", "Bounds\n x = inf\n"),
        lp("x", " x <= 1\n a: x >= 0\n", ""),
        lp("0", "", "Binary\n x x\n"),
        lp("min", "", ""),
        "min\n0\nst\n".into(),
        "min\n0\nend\n".into(),
        lp("0", "", "") + "tail\n",
    ];
    for s in cases {
        assert!(parse_lp(&s).is_err(), "accepted unsupported input: {s}");
    }
}

#[test]
fn limits_are_resource_errors() {
    let s = lp("1e999999 x", "", "");
    assert!(parse_lp(&s).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let s = lp(&format!("0 {}", "x".repeat(1025)), "", "");
    assert!(parse_lp(&s).unwrap_err().starts_with("RESOURCE_LIMIT"));
    let s = lp(&format!("0 x{}", " ".repeat(32768)), "", "");
    assert!(parse_lp(&s).unwrap_err().starts_with("RESOURCE_LIMIT"));
}

#[test]
fn deterministic_lp_mutations_are_total() {
    let source = lp(
        "1/3 x + .2 y + 1",
        " c: x - y <= 4\n",
        "Bounds\n x free\nBinary\n y\n",
    )
    .into_bytes();
    let mut state = 0x5250584c5031u64;
    for case in 0..2000 {
        let mut bytes = source.clone();
        for _ in 0..=case % 7 {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            let id = state as usize % bytes.len();
            bytes[id] = (state >> 32) as u8 & 127;
        }
        let s = String::from_utf8(bytes).unwrap();
        let result = std::panic::catch_unwind(|| parse_lp(&s));
        assert!(result.is_ok(), "panic at case {case}");
        if let Ok(m) = result.unwrap() {
            m.validate().unwrap();
        }
    }
}

// Oracle scalars are generated by Python Fraction, then reconstructed without
// the production decimal/fraction parser being used for expected values.
fn oracle_q(value: &serde_json::Value) -> Q {
    let s = value.as_str().unwrap();
    let (n, d) = s.split_once('/').unwrap_or((s, "1"));
    Q::new(n.parse::<BigInt>().unwrap(), d.parse::<BigInt>().unwrap())
}
fn oracle_expr(v: &serde_json::Value) -> Expr {
    Expr {
        constant: oracle_q(&v["constant"]),
        terms: v["terms"]
            .as_array()
            .unwrap()
            .iter()
            .map(|t| (t[0].as_u64().unwrap() as u32, oracle_q(&t[1])))
            .collect(),
    }
}
fn oracle_option(v: &serde_json::Value) -> Option<Q> {
    if v.is_null() {
        None
    } else {
        Some(oracle_q(v))
    }
}

#[test]
fn python_fraction_generated_models_match() {
    let cases: serde_json::Value =
        serde_json::from_str(include_str!("../../../tests/vectors/lp_oracle.json")).unwrap();
    for case in cases["cases"].as_array().unwrap() {
        let v = &case["expected"];
        let expected = Model {
            name: "LP".into(),
            vars: v["vars"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| Var {
                    name: v["name"].as_str().unwrap().into(),
                    integer: v["integer"].as_bool().unwrap(),
                    lower: oracle_option(&v["lower"]),
                    upper: oracle_option(&v["upper"]),
                })
                .collect(),
            rows: v["rows"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| Row {
                    name: v["name"].as_str().unwrap().into(),
                    expr: oracle_expr(&v["expr"]),
                    lower: oracle_option(&v["lower"]),
                    upper: oracle_option(&v["upper"]),
                })
                .collect(),
            objective: oracle_expr(&v["objective"]),
        };
        assert_eq!(
            parse_lp(case["lp"].as_str().unwrap()).unwrap(),
            expected,
            "oracle case {}",
            case["id"]
        );
    }
    assert!(Q::one() > Q::zero());
}
