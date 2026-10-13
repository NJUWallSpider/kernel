use kernel_core::injectivity::prepare_domain;
use kernel_core::model::{parse_q, Expr, Model, Row, Var, Q};
use kernel_core::verify::Limits;
use serde::Deserialize;

fn q(s: &str) -> Q {
    parse_q(s).unwrap()
}
fn e(c: &str, t: &[(u32, &str)]) -> Expr {
    Expr {
        constant: q(c),
        terms: t.iter().map(|(i, c)| (*i, q(c))).collect(),
    }
}
fn model(n: usize) -> Model {
    Model {
        name: "paired-builder".into(),
        vars: (0..n)
            .map(|i| Var {
                name: format!("x{i}"),
                integer: i % 2 == 0,
                lower: None,
                upper: None,
            })
            .collect(),
        rows: vec![],
        objective: Expr::zero(),
    }
}
fn eval(e: &Expr, v: &[Q]) -> Q {
    e.terms
        .iter()
        .fold(e.constant.clone(), |s, (i, c)| s + c * &v[*i as usize])
}
fn feasible(m: &Model, v: &[Q], integer: bool) -> bool {
    v.len() == m.vars.len()
        && m.vars.iter().zip(v).all(|(x, q)| {
            (!integer || !x.integer || q.is_integer())
                && x.lower.as_ref().is_none_or(|l| q >= l)
                && x.upper.as_ref().is_none_or(|u| q <= u)
        })
        && m.rows.iter().all(|r| {
            let q = eval(&r.expr, v);
            r.lower.as_ref().is_none_or(|l| &q >= l) && r.upper.as_ref().is_none_or(|u| &q <= u)
        })
}

#[test]
fn complete_rows_domains_affine_constants_and_all_goals_are_bound() {
    let mut input = model(3);
    input.vars[0].lower = Some(q("0"));
    input.vars[0].upper = Some(q("1"));
    input.vars[1].lower = Some(q("-2/3"));
    input.vars[2].upper = Some(q("7/5"));
    input.rows = vec![
        Row {
            name: "range".into(),
            expr: e("2/7", &[(0, "1/3"), (2, "-5/11")]),
            lower: Some(q("-1/2")),
            upper: Some(q("4/3")),
        },
        Row {
            name: "equality".into(),
            expr: e("5/2", &[(1, "1"), (2, "-1")]),
            lower: Some(q("3")),
            upper: Some(q("3")),
        },
    ];
    input.objective = e("91/13", &[(0, "-2"), (1, "1/2")]);
    let map = vec![e("7/11", &[(0, "2/3"), (2, "-1/5")]), e("-5/7", &[])];
    let result = prepare_domain(&input, &model(2), &map, &Limits::default()).unwrap();
    assert_eq!(result.model.vars.len(), 6);
    assert_eq!(result.model.rows.len(), 6);
    assert_eq!(result.model.objective, Expr::zero());
    for copy in 0..2 {
        for i in 0..3 {
            let actual = &result.model.vars[copy * 3 + i];
            assert_eq!(actual.integer, input.vars[i].integer);
            assert_eq!(actual.lower, input.vars[i].lower);
            assert_eq!(actual.upper, input.vars[i].upper);
        }
        for r in 0..2 {
            let actual = &result.model.rows[copy * 2 + r];
            let original = &input.rows[r];
            assert_eq!(actual.expr.constant, original.expr.constant);
            assert_eq!(
                actual.expr.terms,
                original
                    .expr
                    .terms
                    .iter()
                    .map(|(i, c)| (*i + copy as u32 * 3, c.clone()))
                    .collect::<Vec<_>>()
            );
            assert_eq!(actual.lower, original.lower);
            assert_eq!(actual.upper, original.upper);
        }
    }
    assert_eq!(
        result.model.rows[4].expr,
        e("0", &[(0, "2/3"), (2, "-1/5"), (3, "-2/3"), (5, "1/5")])
    );
    assert_eq!(result.model.rows[5].expr, Expr::zero());
    assert_eq!(
        result.equalities,
        vec![
            e("0", &[(0, "1"), (3, "-1")]),
            e("0", &[(1, "1"), (4, "-1")]),
            e("0", &[(2, "1"), (5, "-1")])
        ]
    );
    result.model.validate().unwrap();
}

#[test]
fn noninjective_map_and_unobserved_free_auxiliary_still_have_nonempty_fibers() {
    let input = model(2);
    let map = vec![e("4/9", &[(0, "1")])];
    let result = prepare_domain(&input, &model(1), &map, &Limits::default()).unwrap();
    let values = vec![q("1"), q("1/3"), q("1"), q("2/3")];
    assert!(feasible(&result.model, &values, true));
    assert_eq!(eval(&result.equalities[0], &values), q("0"));
    assert_ne!(eval(&result.equalities[1], &values), q("0"));
    // A valid paired model does not mean that its equality goals hold.
    let no_observations = prepare_domain(&input, &model(0), &[], &Limits::default()).unwrap();
    assert_eq!(no_observations.model.rows.len(), 0);
    assert_eq!(no_observations.equalities.len(), 2);
}

#[test]
fn lp_menu_collision_is_retained_and_declared_integrality_is_not_fabricated() {
    let mut input = model(3);
    for v in &mut input.vars {
        v.integer = true;
        v.lower = Some(q("0"));
        v.upper = Some(q("1"));
    }
    input.rows.push(Row {
        name: "pack".into(),
        expr: e("0", &[(0, "1"), (1, "1"), (2, "1")]),
        lower: None,
        upper: Some(q("1")),
    });
    let map = vec![
        e("0", &[(0, "1"), (1, "1"), (2, "1")]),
        e("0", &[(1, "1"), (2, "2")]),
    ];
    let result = prepare_domain(&input, &model(2), &map, &Limits::default()).unwrap();
    let point = ["0", "1", "0", "1/2", "0", "1/2"].map(q);
    assert!(feasible(&result.model, &point, false));
    assert!(!feasible(&result.model, &point, true));
    assert!(result.equalities.iter().any(|e| eval(e, &point) != q("0")));
}

#[test]
fn empty_dimensions_contradictory_bounds_and_constant_observations_preserve_domain() {
    let empty = prepare_domain(
        &model(0),
        &model(2),
        &[e("2/3", &[]), e("-1", &[])],
        &Limits::default(),
    )
    .unwrap();
    assert!(empty.equalities.is_empty());
    assert!(empty.model.vars.is_empty());
    assert_eq!(empty.model.rows.len(), 2);
    assert!(feasible(&empty.model, &[], true));
    let mut bad = model(1);
    bad.vars[0].lower = Some(q("1"));
    bad.vars[0].upper = Some(q("0"));
    let domain = prepare_domain(&bad, &model(0), &[], &Limits::default()).unwrap();
    assert_eq!(domain.model.vars[1].lower, Some(q("1")));
    assert_eq!(domain.model.vars[1].upper, Some(q("0")));
    assert!(!feasible(&domain.model, &[q("0"), q("0")], true));
}

#[test]
fn dimensions_noncanonical_coefficients_and_shared_work_are_checked() {
    let input = model(2);
    let output = model(1);
    let map = vec![e("1/3", &[(0, "1"), (1, "-2/3")])];
    assert!(prepare_domain(&input, &output, &[], &Limits::default()).is_err());
    assert!(prepare_domain(&input, &model(0), &map, &Limits::default()).is_err());
    let mut bad = map.clone();
    bad[0].terms[0].0 = 2;
    assert!(prepare_domain(&input, &output, &bad, &Limits::default()).is_err());
    let mut bad = map.clone();
    bad[0].constant = Q::new_raw(2.into(), 2.into());
    assert!(prepare_domain(&input, &output, &bad, &Limits::default()).is_err());
    let mut bad_model = input.clone();
    bad_model.vars[0].upper = Some(Q::new_raw(1.into(), 0.into()));
    assert!(prepare_domain(&bad_model, &output, &map, &Limits::default()).is_err());
    let result = prepare_domain(&input, &output, &map, &Limits::default()).unwrap();
    assert!(prepare_domain(
        &input,
        &output,
        &map,
        &Limits {
            work: result.statistics.work - 1,
            ..Limits::default()
        }
    )
    .unwrap_err()
    .contains("RESOURCE_LIMIT"));
    assert!(prepare_domain(
        &input,
        &output,
        &map,
        &Limits {
            work: result.statistics.work,
            ..Limits::default()
        }
    )
    .is_ok());
}

#[derive(Deserialize)]
struct Oracle {
    seed: u32,
    cases: Vec<Case>,
}
#[derive(Deserialize)]
struct Case {
    source: Source,
    map: Vec<Expr>,
    expected_rows: Vec<OracleRow>,
    pairs: Vec<Pair>,
}
#[derive(Deserialize)]
struct Source {
    vars: Vec<OracleVar>,
    rows: Vec<OracleRow>,
    objective: Expr,
}
#[derive(Deserialize)]
struct OracleVar {
    integer: bool,
    lower: Option<String>,
    upper: Option<String>,
}
#[derive(Deserialize)]
struct OracleRow {
    expr: Expr,
    lower: Option<String>,
    upper: Option<String>,
}
#[derive(Deserialize)]
struct Pair {
    values: Vec<String>,
    lp: bool,
    integer: bool,
    equalities: Vec<String>,
}
#[test]
fn independent_fraction_oracle_80_complete_models_and_640_point_pairs() {
    let oracle: Oracle = serde_json::from_str(include_str!(
        "../../../tests/vectors/injectivity_oracle.json"
    ))
    .unwrap();
    assert_eq!(oracle.seed, 0x4D454E55);
    assert_eq!(oracle.cases.len(), 80);
    let mut count = 0;
    for (ci, case) in oracle.cases.into_iter().enumerate() {
        let input = Model {
            name: format!("oracle{ci}"),
            vars: case
                .source
                .vars
                .iter()
                .enumerate()
                .map(|(i, v)| Var {
                    name: format!("x{i}"),
                    integer: v.integer,
                    lower: v.lower.as_ref().map(|s| q(s)),
                    upper: v.upper.as_ref().map(|s| q(s)),
                })
                .collect(),
            rows: case
                .source
                .rows
                .iter()
                .enumerate()
                .map(|(i, r)| Row {
                    name: format!("r{i}"),
                    expr: r.expr.clone(),
                    lower: r.lower.as_ref().map(|s| q(s)),
                    upper: r.upper.as_ref().map(|s| q(s)),
                })
                .collect(),
            objective: case.source.objective,
        };
        let result = prepare_domain(
            &input,
            &model(case.map.len()),
            &case.map,
            &Limits::default(),
        )
        .unwrap();
        assert_eq!(result.model.rows.len(), case.expected_rows.len());
        for (actual, expected) in result.model.rows.iter().zip(case.expected_rows) {
            assert_eq!(actual.expr, expected.expr, "case {ci}");
            assert_eq!(actual.lower, expected.lower.as_ref().map(|s| q(s)));
            assert_eq!(actual.upper, expected.upper.as_ref().map(|s| q(s)));
        }
        for pair in case.pairs {
            let values = pair.values.iter().map(|s| q(s)).collect::<Vec<_>>();
            assert_eq!(
                feasible(&result.model, &values, false),
                pair.lp,
                "case {ci}"
            );
            assert_eq!(
                feasible(&result.model, &values, true),
                pair.integer,
                "case {ci}"
            );
            assert_eq!(result.equalities.len(), pair.equalities.len());
            for (e, expected) in result.equalities.iter().zip(pair.equalities) {
                assert_eq!(eval(e, &values), q(&expected));
            }
            count += 1;
        }
    }
    assert_eq!(count, 640);
}
