use kernel_core::flow::prepare_unchecked_extension;
use kernel_core::model::{parse_q, Expr, Model, Row, Var, MAX_Q_BITS, MAX_ROWS, Q};
use kernel_core::point::verify_points;
use kernel_core::proof::{
    Certificate, FlowGroup, FlowWitness, Kind, PointClaim, PointWitness, Ref, Request,
};
use kernel_core::verify::Limits;
use num_bigint::BigInt;
use serde::Deserialize;

fn q(s: &str) -> Q {
    parse_q(s).unwrap()
}
fn model(n: usize) -> Model {
    Model {
        name: "flow-builder".into(),
        vars: (0..n)
            .map(|i| Var {
                name: format!("x{i}"),
                integer: false,
                lower: Some(q("0")),
                upper: None,
            })
            .collect(),
        rows: vec![],
        objective: Expr::zero(),
    }
}
fn one() -> FlowWitness {
    FlowWitness {
        nodes: 2,
        arcs: vec![(0, 1)],
        groups: vec![FlowGroup {
            source: 0,
            commodities: vec![(1, q("1"))],
            flows: vec![Expr::var(0)],
            nonnegative: vec![Ref::Exact],
            balances: vec![Ref::Exact, Ref::Exact],
        }],
    }
}
fn eval(e: &Expr, values: &[Q]) -> Q {
    e.terms.iter().fold(e.constant.clone(), |sum, (i, c)| {
        sum + c * &values[*i as usize]
    })
}
fn point(model: &Model, values: Vec<Q>) -> Result<(), String> {
    let claim = PointClaim::Feasible {
        target: false,
        integers: true,
        objective: None,
    };
    let request = Request { improvements:vec![], bijections:vec![],
        claims: vec![],
        points: vec![claim.clone()],
    };
    let certificate = Certificate { improvements:vec![], bijections:vec![],
        claims: vec![],
        blocks: vec![],
        points: vec![PointWitness {refutation:None, claim, values }],
    };
    verify_points(model, model, &certificate, &request, &Limits::default()).map(|_| ())
}

#[test]
fn extension_is_explicitly_unchecked_and_preserves_input_prefix() {
    let mut input = model(1);
    input.vars[0].integer = true;
    input.vars[0].upper = Some(q("7"));
    input.objective = Expr {
        constant: q("3/11"),
        terms: vec![(0, q("2/7"))],
    };
    let result = prepare_unchecked_extension(&input, &one(), &Limits::default()).unwrap();
    assert_eq!(
        &result.model.vars[..input.vars.len()],
        input.vars.as_slice()
    );
    assert_eq!(result.model.objective, input.objective);
    assert_eq!(result.model.name, input.name);
    assert_eq!(result.statistics.generated_variables, 1);
    assert_eq!(result.statistics.generated_rows, 3);
    assert_eq!(result.statistics.generated_terms, 4);
    assert!(!result.model.vars[1].integer);
    assert_eq!(result.model.vars[1].lower, Some(q("0")));
    assert_eq!(result.model.vars[1].upper, None);
    // The builder returns claims needing proof even though Exact cannot prove
    // these equalities on the entire unconstrained input. Its output is no seal.
    assert_eq!(result.premises.len(), 3);
    assert!(result
        .premises
        .iter()
        .any(|p| p.kind == Kind::Eq && eval(&p.expression, &[q("2")]) != q("0")));
    assert!(point(&result.model, vec![q("1"), q("1")]).is_ok());
    assert!(point(&result.model, vec![q("2"), q("2")]).is_err());
}

#[test]
fn affine_flow_constants_parallel_arcs_and_loops_are_exact() {
    let input = model(1);
    let witness = FlowWitness {
        nodes: 2,
        arcs: vec![(0, 1), (1, 0), (0, 0), (0, 1)],
        groups: vec![FlowGroup {
            source: 0,
            commodities: vec![(1, q("1/3")), (0, q("5/7"))],
            flows: vec![
                Expr {
                    constant: q("1/3"),
                    terms: vec![(0, q("2"))],
                },
                Expr {
                    constant: q("0"),
                    terms: vec![(0, q("2"))],
                },
                Expr {
                    constant: q("7/13"),
                    terms: vec![],
                },
                Expr::zero(),
            ],
            nonnegative: vec![Ref::Exact; 4],
            balances: vec![Ref::Exact; 2],
        }],
    };
    let result = prepare_unchecked_extension(&input, &witness, &Limits::default()).unwrap();
    let old = vec![q("1/2")];
    for p in &result.premises {
        let at = eval(&p.expression, &old);
        assert!(match p.kind {
            Kind::Le => at <= q("0"),
            Kind::Eq => at == q("0"),
            Kind::Int => false,
        });
    }
    // First commodity receives the reverse-edge circulation and the loop.
    let values = vec![
        q("1/2"),
        q("4/3"),
        q("1"),
        q("7/13"),
        q("0"),
        q("0"),
        q("0"),
        q("0"),
        q("0"),
    ];
    assert!(point(&result.model, values).is_ok());
    assert_eq!(
        result.model.rows[2].expr.terms,
        vec![(5, q("1")), (6, q("-1")), (8, q("1"))]
    );
    assert_eq!(result.model.rows[2].lower, Some(q("0"))); // source=sink demand cancels
}

#[test]
fn malformed_graph_dimensions_domains_and_premises_reject() {
    let input = model(1);
    let base = one();
    let mut invalid = Vec::new();
    let mut w = base.clone();
    w.nodes = 0;
    invalid.push(w);
    let mut w = base.clone();
    w.groups.clear();
    invalid.push(w);
    let mut w = base.clone();
    w.arcs[0].1 = 2;
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].source = 2;
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].commodities.clear();
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].commodities[0].0 = 2;
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].commodities[0].1 = q("-1");
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].commodities[0].1 = Q::new_raw(2.into(), 2.into());
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].flows.clear();
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].nonnegative.clear();
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].balances.pop();
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].balances.push(Ref::Exact);
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].flows[0] = Expr::var(1);
    invalid.push(w);
    let mut w = base.clone();
    w.groups[0].flows[0].terms = vec![(0, q("0"))];
    invalid.push(w);
    for (i, w) in invalid.into_iter().enumerate() {
        assert!(
            prepare_unchecked_extension(&input, &w, &Limits::default()).is_err(),
            "mutation {i}"
        );
    }
}

#[test]
fn work_dimensions_and_intermediate_demands_are_bounded() {
    let input = model(1);
    let witness = one();
    let result = prepare_unchecked_extension(&input, &witness, &Limits::default()).unwrap();
    assert!(prepare_unchecked_extension(
        &input,
        &witness,
        &Limits {
            work: result.statistics.work - 1,
            ..Limits::default()
        }
    )
    .unwrap_err()
    .contains("RESOURCE_LIMIT"));
    assert!(prepare_unchecked_extension(
        &input,
        &witness,
        &Limits {
            work: result.statistics.work,
            ..Limits::default()
        }
    )
    .is_ok());
    let mut w = one();
    w.nodes = MAX_ROWS as u32 + 1;
    assert!(prepare_unchecked_extension(&input, &w, &Limits::default())
        .unwrap_err()
        .contains("RESOURCE_LIMIT"));
    let big = Q::from_integer(BigInt::from(1u8) << (MAX_Q_BITS as usize - 1));
    let mut w = one();
    w.groups[0].commodities = vec![(1, big.clone()), (1, big)];
    assert!(prepare_unchecked_extension(&input, &w, &Limits::default())
        .unwrap_err()
        .contains("RESOURCE_LIMIT"));
}

#[test]
fn generated_names_do_not_conflict_with_actual_model_names() {
    let mut input = model(1);
    input.vars[0].name = "$rpx_flow_var_1".into();
    input.rows.push(Row {
        name: "$rpx_flow_row_1".into(),
        expr: Expr::zero(),
        lower: Some(q("0")),
        upper: Some(q("0")),
    });
    let result = prepare_unchecked_extension(&input, &one(), &Limits::default()).unwrap();
    result.model.validate().unwrap();
    assert_eq!(result.model.vars[0], input.vars[0]);
    assert_eq!(result.model.rows[0], input.rows[0]);
    assert_ne!(result.model.vars[1].name, input.vars[0].name);
    assert_ne!(result.model.rows[1].name, input.rows[0].name);
}

#[derive(Deserialize)]
struct Oracle {
    seed: u32,
    cases: Vec<Case>,
}
#[derive(Deserialize)]
struct Case {
    nodes: u32,
    arcs: Vec<(u32, u32)>,
    groups: Vec<Group>,
}
#[derive(Deserialize)]
struct Group {
    source: u32,
    commodities: Vec<(u32, String)>,
    aggregate: Vec<String>,
    constructed: Vec<Vec<String>>,
    extractions: usize,
    circulation_arc_total: String,
}

#[test]
fn independent_fraction_joint_construction_97_vectors() {
    let oracle: Oracle =
        serde_json::from_str(include_str!("../../../tests/vectors/flow_oracle.json")).unwrap();
    assert_eq!(oracle.seed, 0x464c4f57);
    assert_eq!(oracle.cases.len(), 97);
    let mut group_count = 0;
    for (case_index, case) in oracle.cases.into_iter().enumerate() {
        let m = case.arcs.len();
        let input = model(case.groups.len() * m);
        let groups = case
            .groups
            .iter()
            .enumerate()
            .map(|(g, data)| FlowGroup {
                source: data.source,
                commodities: data
                    .commodities
                    .iter()
                    .map(|(sink, demand)| (*sink, q(demand)))
                    .collect(),
                flows: (0..m).map(|e| Expr::var((g * m + e) as u32)).collect(),
                nonnegative: vec![Ref::Exact; m],
                balances: vec![Ref::Exact; case.nodes as usize],
            })
            .collect();
        let witness = FlowWitness {
            nodes: case.nodes,
            arcs: case.arcs,
            groups,
        };
        let old: Vec<Q> = case
            .groups
            .iter()
            .flat_map(|g| g.aggregate.iter().map(|v| q(v)))
            .collect();
        let result = prepare_unchecked_extension(&input, &witness, &Limits::default()).unwrap();
        for premise in &result.premises {
            let value = eval(&premise.expression, &old);
            assert!(
                match premise.kind {
                    Kind::Le => value <= q("0"),
                    Kind::Eq => value == q("0"),
                    Kind::Int => false,
                },
                "case {case_index}, {premise:?}"
            );
        }
        let mut all_values = old;
        for group in &case.groups {
            group_count += 1;
            assert!(group.extractions <= m + group.commodities.len());
            assert!(q(&group.circulation_arc_total) >= q("0"));
            all_values.extend(group.constructed.iter().flatten().map(|v| q(v)));
        }
        assert_eq!(all_values.len(), result.model.vars.len());
        point(&result.model, all_values)
            .unwrap_or_else(|error| panic!("case {case_index}: {error}"));
    }
    assert_eq!(group_count, 186);
}
