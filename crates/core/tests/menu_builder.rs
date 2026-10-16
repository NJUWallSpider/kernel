use crate::menu::prepare_unchecked_extension;
use crate::model::{parse_q, Expr, Model, Row, Var, MAX_Q_BITS, Q};
use crate::proof::{Kind, MenuWitness, Ref};
use crate::verify::Limits;
use num_bigint::BigInt;
use serde::Deserialize;

fn q(s: &str) -> Q {
    parse_q(s).unwrap()
}
fn e(c: &str, terms: &[(u32, &str)]) -> Expr {
    Expr {
        constant: q(c),
        terms: terms.iter().map(|(i, c)| (*i, q(c))).collect(),
    }
}
fn model(n: usize) -> Model {
    Model {
        name: "menu-builder".into(),
        vars: (0..n)
            .map(|i| Var {
                name: format!("x{i}"),
                integer: false,
                lower: None,
                upper: None,
            })
            .collect(),
        rows: vec![],
        objective: Expr::zero(),
    }
}
fn witness(k: u32, a: Expr, i: Expr) -> MenuWitness {
    MenuWitness {
        maximum_index: k,
        activation: a,
        index: i,
        checks: (0..6).map(Ref::Local).collect(),
    }
}
fn eval(e: &Expr, v: &[Q]) -> Q {
    e.terms
        .iter()
        .fold(e.constant.clone(), |s, (i, c)| s + c * &v[*i as usize])
}
fn feasible(m: &Model, v: &[Q]) -> bool {
    v.len() == m.vars.len()
        && m.vars.iter().zip(v).all(|(x, q)| {
            (!x.integer || q.is_integer())
                && x.lower.as_ref().is_none_or(|l| q >= l)
                && x.upper.as_ref().is_none_or(|u| q <= u)
        })
        && m.rows.iter().all(|r| {
            let q = eval(&r.expr, v);
            r.lower.as_ref().is_none_or(|l| &q >= l) && r.upper.as_ref().is_none_or(|u| &q <= u)
        })
}

#[test]
fn exact_six_premises_and_binary_rows_include_singleton() {
    let input = model(2);
    let result = prepare_unchecked_extension(
        &input,
        &[
            witness(2, e("1/3", &[(0, "2")]), e("-2/7", &[(0, "-1"), (1, "3")])),
            witness(0, Expr::var(1), Expr::zero()),
        ],
        &Limits::default(),
    )
    .unwrap();
    let expected = [
        e("-1/3", &[(0, "-2")]),
        e("-2/3", &[(0, "2")]),
        e("1/3", &[(0, "2")]),
        e("2/7", &[(0, "1"), (1, "-3")]),
        e("-20/21", &[(0, "-5"), (1, "3")]),
        e("-2/7", &[(0, "-1"), (1, "3")]),
    ];
    for (i, p) in result.premises[..6].iter().enumerate() {
        assert_eq!(
            p.kind,
            if i == 2 || i == 5 {
                Kind::Int
            } else {
                Kind::Le
            }
        );
        assert_eq!(p.reference, Ref::Local(i as u32));
        assert_eq!(p.expression, expected[i]);
    }
    assert_eq!(result.model.vars.len(), 6);
    assert_eq!(result.model.rows.len(), 4);
    assert!(result.model.vars[2..]
        .iter()
        .all(|v| v.integer && v.lower == Some(q("0")) && v.upper == Some(q("1"))));
    assert_eq!(
        result.model.rows[0].expr,
        e("-1/3", &[(0, "-2"), (2, "1"), (3, "1"), (4, "1")])
    );
    assert_eq!(
        result.model.rows[1].expr,
        e("2/7", &[(0, "1"), (1, "-3"), (3, "1"), (4, "2")])
    );
    assert_eq!(result.model.rows[2].expr, e("0", &[(1, "-1"), (5, "1")]));
    assert_eq!(result.model.rows[3].expr, Expr::zero());
    assert!(result
        .model
        .rows
        .iter()
        .all(|r| r.lower == Some(q("0")) && r.upper == Some(q("0"))));
}

#[test]
fn inactive_and_index_zero_are_distinct_and_all_valid_indices_exist() {
    for k in 0..13 {
        for a in 0..2 {
            for i in 0..=if a == 0 { 0 } else { k } {
                let extension = prepare_unchecked_extension(
                    &model(0),
                    &[witness(k, e(&a.to_string(), &[]), e(&i.to_string(), &[]))],
                    &Limits::default(),
                )
                .unwrap();
                let mut values = vec![q("0"); k as usize + 1];
                if a == 1 {
                    values[i as usize] = q("1");
                }
                assert!(feasible(&extension.model, &values));
                let mut matches = 0;
                for bits in 0..(1usize << (k + 1)) {
                    let candidate = (0..=k)
                        .map(|j| if bits & (1 << j) == 0 { q("0") } else { q("1") })
                        .collect::<Vec<_>>();
                    matches += usize::from(feasible(&extension.model, &candidate));
                }
                assert_eq!(matches, 1, "K={k}, A={a}, I={i}");
            }
        }
    }
}

#[test]
fn false_premises_are_not_certified_by_structural_preparation() {
    for (a, i) in [
        ("1/2", "0"),
        ("1", "1/2"),
        ("0", "1"),
        ("1", "-1"),
        ("1", "3"),
        ("2", "1"),
    ] {
        let extension = prepare_unchecked_extension(
            &model(0),
            &[witness(2, e(a, &[]), e(i, &[]))],
            &Limits::default(),
        )
        .unwrap();
        assert!(extension.premises.iter().any(|p| match p.kind {
            Kind::Int => !p.expression.constant.is_integer(),
            Kind::Le => p.expression.constant > q("0"),
            Kind::Eq => false,
        }));
        // A=2,I=1 does admit two selected binary options; the false upper-A
        // premise is exactly what prevents that unsupported extension being used.
        if a != "2" {
            for bits in 0..8 {
                let v = (0..3)
                    .map(|j| if bits & (1 << j) == 0 { q("0") } else { q("1") })
                    .collect::<Vec<_>>();
                assert!(!feasible(&extension.model, &v));
            }
        }
    }
}

#[test]
fn original_prefix_empty_family_and_generated_names_are_exact() {
    let mut input = model(1);
    input.vars[0].name = "$rpx_menu_var_1".into();
    input.vars[0].integer = true;
    input.vars[0].lower = Some(q("-2"));
    input.vars[0].upper = Some(q("3"));
    input.rows.push(Row {
        name: "$rpx_menu_row_1".into(),
        expr: e("3/5", &[(0, "-2/3")]),
        lower: Some(q("-1")),
        upper: Some(q("4")),
    });
    input.objective = e("9/11", &[(0, "7/13")]);
    let empty = prepare_unchecked_extension(&input, &[], &Limits::default()).unwrap();
    assert_eq!(empty.model, input);
    let result = prepare_unchecked_extension(
        &input,
        &[witness(1, Expr::var(0), Expr::var(0))],
        &Limits::default(),
    )
    .unwrap();
    assert_eq!(result.model.vars[0], input.vars[0]);
    assert_eq!(result.model.rows[0], input.rows[0]);
    assert_eq!(result.model.objective, input.objective);
    assert_eq!(result.model.name, input.name);
    result.model.validate().unwrap();
}

#[test]
fn malformed_parent_coordinates_counts_scalars_and_budget_reject() {
    let input = model(1);
    let base = witness(2, Expr::var(0), Expr::var(0));
    for change in 0..6 {
        let mut m = base.clone();
        match change {
            0 => m.activation = Expr::var(1),
            1 => m.index = Expr::var(2),
            2 => m.checks.pop().map(|_| ()).unwrap(),
            3 => m.checks.push(Ref::Exact),
            4 => m.activation.constant = Q::new_raw(2.into(), 2.into()),
            _ => m.index.terms = vec![(0, q("0"))],
        };
        assert!(prepare_unchecked_extension(&input, &[m], &Limits::default()).is_err());
    }
    let huge = witness(u32::MAX, Expr::zero(), Expr::zero());
    assert!(
        prepare_unchecked_extension(&input, &[huge], &Limits::default())
            .unwrap_err()
            .contains("RESOURCE_LIMIT")
    );
    let normal = prepare_unchecked_extension(&input, &[base.clone()], &Limits::default()).unwrap();
    assert!(prepare_unchecked_extension(
        &input,
        &[base.clone()],
        &Limits {
            work: normal.statistics.work - 1,
            ..Limits::default()
        }
    )
    .unwrap_err()
    .contains("RESOURCE_LIMIT"));
    assert!(prepare_unchecked_extension(
        &input,
        &[base],
        &Limits {
            work: normal.statistics.work,
            ..Limits::default()
        }
    )
    .is_ok());
    let big = Q::from_integer(BigInt::from(1u8) << (MAX_Q_BITS as usize - 1));
    for constant in [false, true] {
        let a = if constant {
            Expr {
                constant: big.clone(),
                terms: vec![],
            }
        } else {
            Expr {
                constant: q("0"),
                terms: vec![(0, big.clone())],
            }
        };
        let m = witness(2, a, Expr::zero());
        assert!(
            prepare_unchecked_extension(&input, &[m], &Limits::default())
                .unwrap_err()
                .contains("RESOURCE_LIMIT")
        );
    }
}

#[derive(Deserialize)]
struct Oracle {
    seed: u32,
    cases: Vec<Case>,
    binary_vectors_enumerated: usize,
    unique_menu_states: usize,
}
#[derive(Deserialize)]
struct Case {
    input: Vec<String>,
    menus: Vec<Menu>,
    accept: bool,
    constructed: Vec<String>,
}
#[derive(Deserialize)]
struct Menu {
    maximum_index: u32,
    activation: Expr,
    index: Expr,
    premise_values: Vec<String>,
}
#[test]
fn independent_fraction_oracle_241_menu_families() {
    let oracle: Oracle =
        serde_json::from_str(include_str!("../../../tests/vectors/menu_oracle.json")).unwrap();
    assert_eq!(oracle.seed, 0x4D454E55);
    assert_eq!(oracle.cases.len(), 241);
    assert_eq!(oracle.binary_vectors_enumerated, 16382);
    assert_eq!(oracle.unique_menu_states, 104);
    let mut accepted = 0;
    for (ci, case) in oracle.cases.into_iter().enumerate() {
        let menus = case
            .menus
            .iter()
            .map(|m| witness(m.maximum_index, m.activation.clone(), m.index.clone()))
            .collect::<Vec<_>>();
        let extension =
            prepare_unchecked_extension(&model(case.input.len()), &menus, &Limits::default())
                .unwrap();
        let mut values = case.input.iter().map(|s| q(s)).collect::<Vec<_>>();
        let mut accept = true;
        let expected = case.menus.iter().flat_map(|m| &m.premise_values);
        for (premise, expected) in extension.premises.iter().zip(expected) {
            let value = eval(&premise.expression, &values);
            assert_eq!(value, q(expected), "case {ci}");
            accept &= if premise.kind == Kind::Int {
                value.is_integer()
            } else {
                value <= q("0")
            };
        }
        assert_eq!(accept, case.accept, "case {ci}");
        values.extend(case.constructed.iter().map(|s| q(s)));
        assert_eq!(
            feasible(&extension.model, &values),
            case.accept,
            "case {ci}"
        );
        accepted += usize::from(accept);
    }
    assert_eq!(accepted, 121);
}
