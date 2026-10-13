use num_bigint::BigInt;
use num_traits::{One, Zero};
use serde::Deserialize;
use kernel_core::{
    model::{Expr, MAX_Q_BITS, MAX_ROWS, Model, Q, Row, Var, parse_q},
    proof::{Kind, Ref, SubflowGroup, SubflowWitness},
    subflow::{UncheckedSubflowExtension, prepare_unchecked_extension},
    verify::Limits,
};

fn q(s: &str) -> Q {
    parse_q(s).unwrap()
}
fn e(c: &str, terms: &[(u32, &str)]) -> Expr {
    Expr {
        constant: q(c),
        terms: terms.iter().map(|(i, v)| (*i, q(v))).collect(),
    }
}
fn model(n: usize) -> Model {
    Model {
        name: "subflow-audit".into(),
        vars: (0..n)
            .map(|i| Var {
                name: format!("f{i}"),
                integer: false,
                lower: Some(Q::zero()),
                upper: None,
            })
            .collect(),
        rows: vec![],
        objective: Expr::zero(),
    }
}
fn one() -> SubflowWitness {
    SubflowWitness {
        nodes: 2,
        arcs: vec![(0, 1)],
        groups: vec![SubflowGroup {
            source: 0,
            demands: vec![(1, Q::one())],
            flows: vec![Expr::var(0)],
            nonnegative: vec![Ref::Local(11)],
            balances: vec![Ref::Local(12), Ref::Local(13)],
        }],
    }
}
fn eval(e: &Expr, values: &[Q]) -> Q {
    e.terms
        .iter()
        .fold(e.constant.clone(), |a, (i, v)| a + v * &values[*i as usize])
}
fn feasible(m: &Model, x: &[Q]) -> bool {
    x.len() == m.vars.len()
        && m.vars.iter().zip(x).all(|(v, x)| {
            (!v.integer || x.is_integer())
                && v.lower.as_ref().is_none_or(|a| x >= a)
                && v.upper.as_ref().is_none_or(|a| x <= a)
        })
        && m.rows.iter().all(|r| {
            let x = eval(&r.expr, x);
            r.lower.as_ref().is_none_or(|a| &x >= a) && r.upper.as_ref().is_none_or(|a| &x <= a)
        })
}
fn premises_at(result: &UncheckedSubflowExtension, x: &[Q]) -> bool {
    result.premises.iter().all(|p| {
        let v = eval(&p.expression, x);
        match p.kind {
            Kind::Le => v <= Q::zero(),
            Kind::Eq => v.is_zero(),
            Kind::Int => false,
        }
    })
}
#[derive(Deserialize)]
struct ExpectedPremise {
    kind: String,
    expression: Expr,
}
#[derive(Deserialize)]
struct ExpectedRow {
    expression: Expr,
    lower: Option<String>,
    upper: Option<String>,
}
#[derive(Deserialize)]
struct Path {
    edges: Vec<usize>,
    demand_index: usize,
    amount: String,
}
#[derive(Deserialize)]
#[allow(non_snake_case)]
struct Case {
    nodes: u32,
    arcs: Vec<(u32, u32)>,
    source: u32,
    demands: Vec<(u32, String)>,
    flows: Vec<String>,
    kept: Vec<String>,
    B: String,
    rhs: Vec<String>,
    paths: Vec<Path>,
    premises: Vec<ExpectedPremise>,
    rows: Vec<ExpectedRow>,
}
#[derive(Deserialize)]
struct Oracle {
    cases: Vec<Case>,
}

#[test]
fn fraction_oracle_983_joint_constructions_and_every_symbolic_field() {
    let oracle: Oracle = serde_json::from_str(include_str!("../../../audit/subflow-next/fixtures/oracle.json")).unwrap();
    assert_eq!(oracle.cases.len(), 983);
    for (index, c) in oracle.cases.into_iter().enumerate() {
        let m = c.arcs.len();
        let input = model(m);
        let w = SubflowWitness {
            nodes: c.nodes,
            arcs: c.arcs.clone(),
            groups: vec![SubflowGroup {
                source: c.source,
                demands: c.demands.iter().map(|(v, d)| (*v, q(d))).collect(),
                flows: (0..m).map(|i| Expr::var(i as u32)).collect(),
                nonnegative: (0..m).map(|i| Ref::Local(i as u32)).collect(),
                balances: (0..c.nodes).map(|i| Ref::Local(i + m as u32)).collect(),
            }],
        };
        let r = prepare_unchecked_extension(&input, &w, &Limits::default()).unwrap();
        assert_eq!(r.model.vars[..m], input.vars, "case {index}");
        assert_eq!(r.model.objective, input.objective);
        assert_eq!(r.premises.len(), c.premises.len());
        for (i, (a, b)) in r.premises.iter().zip(&c.premises).enumerate() {
            assert_eq!(a.expression, b.expression, "case {index}, premise {i}");
            assert_eq!(
                a.kind,
                if b.kind == "Le" {
                    Kind::Le
                } else {
                    assert_eq!(b.kind, "Eq");
                    Kind::Eq
                }
            );
            assert_eq!(a.reference, Ref::Local(i as u32));
        }
        assert_eq!(r.model.rows.len(), c.rows.len());
        for (i, (a, b)) in r.model.rows.iter().zip(&c.rows).enumerate() {
            assert_eq!(a.expr, b.expression, "case {index}, row {i}");
            assert_eq!(a.lower, b.lower.as_deref().map(q));
            assert_eq!(a.upper, b.upper.as_deref().map(q));
        }
        assert!(
            r.model.vars[m..]
                .iter()
                .all(|v| !v.integer && v.lower == Some(Q::zero()) && v.upper == Some(q(&c.B)))
        );
        assert_eq!(r.statistics.generated_variables, m as u64);
        assert_eq!(r.statistics.generated_rows, (c.nodes as usize + m) as u64);
        assert_eq!(
            r.statistics.generated_terms,
            r.model
                .rows
                .iter()
                .map(|r| r.expr.terms.len() as u64)
                .sum::<u64>()
        );
        let old = c.flows.iter().map(|v| q(v)).collect::<Vec<_>>();
        assert!(premises_at(&r, &old), "case {index}");
        let all = old
            .iter()
            .cloned()
            .chain(c.kept.iter().map(|v| q(v)))
            .collect::<Vec<_>>();
        assert!(feasible(&r.model, &all), "case {index}");
        // Independently check the extraction witness, without implementing a
        // second path search or deriving expected builder expressions in Rust.
        let mut retained = vec![Q::zero(); m];
        let mut delivered = vec![Q::zero(); c.demands.len()];
        let mut total = Q::zero();
        assert!(c.paths.len() <= m + c.demands.iter().filter(|(_, d)| q(d) > Q::zero()).count());
        for path in c.paths {
            let amount = q(&path.amount);
            assert!(amount > Q::zero());
            let mut node = c.source;
            let mut visited = vec![false; c.nodes as usize];
            visited[node as usize] = true;
            for edge in path.edges {
                assert!(edge < m);
                let (tail, head) = c.arcs[edge];
                assert_eq!(tail, node);
                assert!(!visited[head as usize]);
                visited[head as usize] = true;
                retained[edge] += &amount;
                node = head;
            }
            assert_eq!(node, c.demands[path.demand_index].0);
            delivered[path.demand_index] += &amount;
            total += amount;
        }
        assert_eq!(total, q(&c.B));
        assert_eq!(
            delivered,
            c.demands.iter().map(|(_, d)| q(d)).collect::<Vec<_>>()
        );
        assert_eq!(retained, c.kept.iter().map(|d| q(d)).collect::<Vec<_>>());
        let mut div = vec![Q::zero(); c.nodes as usize];
        for (&(u, v), g) in c.arcs.iter().zip(retained) {
            div[u as usize] += &g;
            div[v as usize] -= g;
        }
        assert_eq!(div, c.rhs.iter().map(|d| q(d)).collect::<Vec<_>>());
    }
}

#[test]
fn unchecked_builder_does_not_certify_false_or_missing_reference_premises() {
    let input = model(1);
    let r = prepare_unchecked_extension(&input, &one(), &Limits::default()).unwrap();
    assert_eq!(
        r.premises
            .iter()
            .map(|p| p.reference.clone())
            .collect::<Vec<_>>(),
        vec![Ref::Local(11), Ref::Local(12), Ref::Local(13)]
    );
    assert!(premises_at(&r, &[q("1")]));
    assert!(!premises_at(&r, &[q("2")]));
    let mut bad = one();
    bad.groups[0].nonnegative[0] = Ref::Local(u32::MAX);
    // Deliberately leaves reference lookup to the future integrated old-scope checker.
    let unchecked = prepare_unchecked_extension(&input, &bad, &Limits::default()).unwrap();
    assert_eq!(unchecked.premises[0].reference, Ref::Local(u32::MAX));
    assert!(!premises_at(&unchecked, &[q("-1")]));
}

#[test]
fn simultaneous_groups_affine_constants_duplicate_sinks_and_prefix_are_exact() {
    let mut input = model(1);
    input.name = "prefix".into();
    input.vars[0].name = "$rpx_subflow_var_1".into();
    input.vars[0].integer = true;
    input.vars[0].upper = Some(q("7"));
    input.objective = e("3/11", &[(0, "2/7")]);
    input.rows.push(Row {
        name: "$rpx_subflow_row_1".into(),
        expr: Expr::var(0),
        lower: Some(q("0")),
        upper: Some(q("7")),
    });
    let group = SubflowGroup {
        source: 0,
        demands: vec![(1, q("1/7")), (1, q("2/7")), (1, q("0"))],
        flows: vec![e("3/7", &[(0, "2")]), e("0", &[(0, "2")]), e("19/13", &[])],
        nonnegative: vec![Ref::Exact; 3],
        balances: vec![Ref::Exact; 2],
    };
    let mut zero = group.clone();
    zero.demands.clear();
    zero.flows[0] = e("0", &[(0, "2")]);
    let w = SubflowWitness {
        nodes: 2,
        arcs: vec![(0, 1), (1, 0), (0, 0)],
        groups: vec![group, zero],
    };
    let r = prepare_unchecked_extension(&input, &w, &Limits::default()).unwrap();
    assert_eq!(r.model.name, input.name);
    assert_eq!(r.model.objective, input.objective);
    assert_eq!(r.model.vars[..1], input.vars);
    assert_eq!(r.model.rows[..1], input.rows);
    assert_eq!(r.model.vars[1].name, "$rpx_subflow_var_2");
    assert_eq!(r.model.rows[1].name, "$rpx_subflow_row_2");
    assert!(premises_at(&r, &[q("1")]));
    assert!(feasible(
        &r.model,
        &[q("1"), q("3/7"), q("0"), q("0"), q("0"), q("0"), q("0")]
    ));
    assert!(r.model.vars[4..].iter().all(|v| v.upper == Some(Q::zero())));
    assert_eq!(r.statistics.generated_variables, 6);
    assert_eq!(r.statistics.generated_rows, 10);
}

#[test]
fn empty_demand_zero_demand_no_arcs_and_source_equal_sink_policy() {
    for demands in [vec![], vec![(1, q("0"))]] {
        let w = SubflowWitness {
            nodes: 2,
            arcs: vec![],
            groups: vec![SubflowGroup {
                source: 0,
                demands,
                flows: vec![],
                nonnegative: vec![],
                balances: vec![Ref::Exact; 2],
            }],
        };
        let r = prepare_unchecked_extension(&model(0), &w, &Limits::default()).unwrap();
        assert!(premises_at(&r, &[]));
        assert!(feasible(&r.model, &[]));
        assert_eq!(r.model.rows.len(), 2);
    }
    let w = SubflowWitness {
        nodes: 1,
        arcs: vec![(0, 0)],
        groups: vec![SubflowGroup {
            source: 0,
            demands: vec![],
            flows: vec![e("19", &[])],
            nonnegative: vec![Ref::Exact],
            balances: vec![Ref::Exact],
        }],
    };
    let r = prepare_unchecked_extension(&model(0), &w, &Limits::default()).unwrap();
    assert!(premises_at(&r, &[]));
    assert!(feasible(&r.model, &[q("0")]));
    for demand in ["0", "1"] {
        let mut bad = one();
        bad.groups[0].demands = vec![(0, q(demand))];
        assert!(
            prepare_unchecked_extension(&model(1), &bad, &Limits::default())
                .unwrap_err()
                .starts_with("INVALID")
        );
    }
    let mut impossible = one();
    impossible.arcs.clear();
    impossible.groups[0].flows.clear();
    impossible.groups[0].nonnegative.clear();
    let r = prepare_unchecked_extension(&model(0), &impossible, &Limits::default()).unwrap();
    assert!(!premises_at(&r, &[]));
    assert!(!feasible(&r.model, &[]));
}

#[test]
fn malformed_middle_group_and_old_scope_expressions_are_rejected() {
    for attack in 0..16 {
        let mut bad = one();
        match attack {
            0 => bad.nodes = 0,
            1 => bad.groups.clear(),
            2 => bad.arcs[0].0 = 2,
            3 => bad.groups[0].source = 2,
            4 => bad.groups[0].demands[0].0 = 2,
            5 => bad.groups[0].demands[0].1 = q("-1"),
            6 => {
                bad.groups[0].nonnegative.clear();
            }
            7 => bad.groups[0].balances.push(Ref::Exact),
            8 => bad.groups[0].flows.clear(),
            9 => bad.groups[0].flows[0] = Expr::var(1),
            10 => bad.groups[0].flows[0].terms.push((0, q("1"))),
            11 => bad.groups[0].flows[0].terms[0].1 = q("0"),
            12 => bad.groups[0].flows[0].constant = Q::new_raw(2.into(), 2.into()),
            13 => bad.groups[0].demands[0].1 = Q::new_raw(1.into(), 0.into()),
            14 => bad.groups[0].flows[0].terms[0].1 = Q::new_raw(1.into(), (-1).into()),
            _ => bad.groups[0].demands[0].0 = 0,
        }
        if !bad.groups.is_empty() {
            bad.groups.insert(0, one().groups.remove(0));
            bad.groups.push(one().groups.remove(0));
        }
        assert!(
            prepare_unchecked_extension(&model(1), &bad, &Limits::default())
                .unwrap_err()
                .starts_with("INVALID"),
            "attack {attack}"
        );
    }
    let mut bad = model(1);
    bad.vars[0].name.clear();
    assert!(
        prepare_unchecked_extension(&bad, &one(), &Limits::default())
            .unwrap_err()
            .starts_with("INVALID")
    );
}

#[test]
fn all_scalar_intermediate_bit_limits_survive_cancellation() {
    let huge = Q::from_integer(BigInt::from(1) << (MAX_Q_BITS as usize - 1));
    // Each input is permitted, but summing two demands has one extra bit.
    let mut w = one();
    w.groups[0].demands = vec![(1, huge.clone()), (1, huge.clone())];
    assert!(
        prepare_unchecked_extension(&model(1), &w, &Limits::default())
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
    for constant in [true, false] {
        let flow = if constant {
            Expr {
                constant: huge.clone(),
                terms: vec![],
            }
        } else {
            Expr {
                constant: Q::zero(),
                terms: vec![(0, huge.clone())],
            }
        };
        let w = SubflowWitness {
            nodes: 2,
            arcs: vec![(0, 1), (0, 1), (1, 0)],
            groups: vec![SubflowGroup {
                source: 0,
                demands: vec![],
                flows: vec![flow.clone(), flow.clone(), flow],
                nonnegative: vec![Ref::Exact; 3],
                balances: vec![Ref::Exact; 2],
            }],
        };
        // Later reverse-flow cancellation cannot hide the earlier huge sum.
        assert!(
            prepare_unchecked_extension(&model(1), &w, &Limits::default())
                .unwrap_err()
                .starts_with("RESOURCE_LIMIT")
        );
    }
    let mut malformed = one();
    malformed.groups[0].flows[0].constant = Q::from_integer(BigInt::from(1) << MAX_Q_BITS as usize);
    assert!(
        prepare_unchecked_extension(&model(1), &malformed, &Limits::default())
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
}

#[test]
fn work_and_dimension_limits_are_preflighted_and_exact_work_is_reusable() {
    let input = model(1);
    let w = one();
    let r = prepare_unchecked_extension(&input, &w, &Limits::default()).unwrap();
    for work in [0, r.statistics.work - 1] {
        assert!(
            prepare_unchecked_extension(
                &input,
                &w,
                &Limits {
                    work,
                    ..Limits::default()
                }
            )
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
        );
    }
    let exact = prepare_unchecked_extension(
        &input,
        &w,
        &Limits {
            work: r.statistics.work,
            ..Limits::default()
        },
    )
    .unwrap();
    assert_eq!(exact.model, r.model);
    let mut bad = w.clone();
    bad.nodes = MAX_ROWS as u32 + 1;
    assert!(
        prepare_unchecked_extension(&input, &bad, &Limits::default())
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT")
    );
    // Expanded rows exceed the ceiling before n-sized divergence buffers exist.
    let mut big = one();
    big.nodes = 1_000_001;
    big.groups[0].balances = vec![Ref::Exact; big.nodes as usize];
    big.groups.push(big.groups[0].clone());
    assert!(
        prepare_unchecked_extension(&input, &big, &Limits::default())
            .unwrap_err()
            .contains("expanded dimensions")
    );
}

#[test]
fn independently_clipping_arcs_and_violating_each_joint_obligation_fail() {
    let input = model(2);
    let w = SubflowWitness {
        nodes: 2,
        arcs: vec![(0, 1), (1, 0)],
        groups: vec![SubflowGroup {
            source: 0,
            demands: vec![(1, q("82"))],
            flows: vec![Expr::var(0), Expr::var(1)],
            nonnegative: vec![Ref::Exact; 2],
            balances: vec![Ref::Exact; 2],
        }],
    };
    let r = prepare_unchecked_extension(&input, &w, &Limits::default()).unwrap();
    assert!(premises_at(&r, &[q("164"), q("82")]));
    assert!(feasible(&r.model, &[q("164"), q("82"), q("82"), q("0")]));
    for (old, g) in [
        (["164", "82"], ["82", "82"]),  // independent clipping destroys balance
        (["164", "82"], ["164", "82"]), // unchanged exceeds global B
        (["82", "0"], ["83", "1"]),     // balanced but exceeds f and B
        (["82", "0"], ["81", "-1"]),
    ] {
        // balanced but negative
        let values = old.into_iter().chain(g).map(q).collect::<Vec<_>>();
        assert!(!feasible(&r.model, &values));
    }
}

#[test]
fn every_node_premise_detects_extra_supply_wrong_orientation_or_negative_flow() {
    let cases = [
        (vec![(0, 2), (1, 2)], vec![e("1", &[]), e("1", &[])], "2"),
        (vec![(2, 0)], vec![e("1", &[])], "1"),
        (vec![(0, 2)], vec![e("-1", &[])], "1"),
        (vec![(0, 2)], vec![e("1", &[])], "2"),
    ];
    for (arcs, flows, demand) in cases {
        let m = arcs.len();
        let w = SubflowWitness {
            nodes: 3,
            arcs,
            groups: vec![SubflowGroup {
                source: 0,
                demands: vec![(2, q(demand))],
                flows,
                nonnegative: vec![Ref::Exact; m],
                balances: vec![Ref::Exact; 3],
            }],
        };
        let r = prepare_unchecked_extension(&model(0), &w, &Limits::default()).unwrap();
        assert_eq!(r.premises.len(), m + 3);
        assert!(!premises_at(&r, &[]));
    }
}

mod integration {
    use super::*;
    use kernel_core::{codec,rpa,proof::*,verify::verify};
    fn fixture()->(Model,Model,Certificate) {
        let mut source=model(3);
        source.rows.push(Row{name:"flow".into(),expr:Expr::var(0),lower:Some(q("2")),upper:Some(q("2"))});
        source.objective=e("7/11",&[(0,"3/7"),(1,"5/13")]);
        let mut target=source.clone();target.name="pruned".into();
        for i in 0..3 {target.vars.push(Var{name:format!("g{i}"),integer:false,lower:Some(q("0")),upper:Some(q("2"))});}
        for (name,ex,rhs) in [("s",e("0",&[(3,"1")]),"2"),("t",e("0",&[(3,"-1")]),"-2"),("isolated",Expr::zero(),"0")] {
            target.rows.push(Row{name:name.into(),expr:ex,lower:Some(q(rhs)),upper:Some(q(rhs))});
        }
        for i in 0..3 {target.rows.push(Row{name:format!("sub{i}"),expr:Expr{constant:q("0"),terms:vec![(i,q("-1")),(3+i,q("1"))]},lower:None,upper:Some(q("0"))});}
        let claim=Claim{input_halfspace:None,input_objective_level:None,affine_projection:vec![],reverse:false,input_integers:false,output_integers:false,objective:Objective::Equal,projection:vec![(0,0),(1,1),(2,2)],inverse:None,input_objective_lower:None};
        let mut checks=(0..3).map(Ref::VarLower).collect::<Vec<_>>();
        for i in 3..6 {checks.extend([Ref::VarLower(i),Ref::VarUpper(i)]);}
        checks.extend((0..4).map(Ref::RowEq));checks.extend((4..7).map(Ref::RowUpper));checks.extend(std::iter::repeat_n(Ref::Exact,4));
        let body=Block{steps:vec![],end:End::Return{map:(0..6).map(Expr::var).collect(),checks}};
        let witness=SubflowWitness{nodes:3,arcs:vec![(0,1),(1,1),(2,2)],groups:vec![SubflowGroup{source:0,demands:vec![(1,q("1")),(1,q("1"))],flows:(0..3).map(Expr::var).collect(),nonnegative:(0..3).map(Ref::VarLower).collect(),balances:vec![Ref::RowEq(0),Ref::Local(0),Ref::Exact]}]};
        let block=Block{steps:vec![Step::Lin{id:0,kind:Kind::Eq,constant:q("0"),terms:vec![(Ref::RowEq(0),q("-1"))]}],end:End::SubflowLift{witness,body:Box::new(body)}};
        (source,target,Certificate{improvements:vec![],bijections:vec![],claims:vec![claim],blocks:vec![block],points:vec![]})
    }
    fn check(s:&Model,t:&Model,c:&Certificate)->Result<kernel_core::verify::Statistics,String> {verify(s,t,c,&c.claims,&Limits::default())}
    #[test] fn complete_joint_subflow_proof_and_v10_wire_roundtrip() {
        let (s,t,c)=fixture();let stats=check(&s,&t,&c).unwrap();
        assert_eq!(stats.subflow_lifts,1);assert_eq!(stats.subflow_generated_variables,3);assert_eq!(stats.subflow_generated_rows,6);
        let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(&bytes[4..6],&10u16.to_le_bytes());assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);
        let text=rpa::disassemble(&c).unwrap();assert!(text.starts_with("RPA 10\n"));assert_eq!(rpa::assemble(&text).unwrap(),c);
        for version in 1u16..10 {let mut b=bytes.clone();b[4..6].copy_from_slice(&version.to_le_bytes());assert!(codec::decode_certificate(&b).is_err());assert!(rpa::assemble(&text.replacen("RPA 10",&format!("RPA {version}"),1)).is_err());}
        for n in 0..bytes.len() {let mut b=bytes[..n].to_vec();if n>=16{b[8..16].copy_from_slice(&(n as u64).to_le_bytes());}assert!(codec::decode_certificate(&b).is_err(),"truncation {n}");}
    }
    #[test] fn all_old_scope_premises_are_discharged_before_any_new_coordinate_exists() {
        let(s,t,c)=fixture();
        for attack in 0..10 {let mut bad=c.clone();if let End::SubflowLift{witness,..}=&mut bad.blocks[0].end {let g=&mut witness.groups[0];match attack {
            0=>g.nonnegative[1]=Ref::VarLower(3),1=>g.balances[1]=Ref::RowEq(2),
            2=>g.flows[1]=Expr::var(3),3=>g.nonnegative[1]=Ref::Local(999),
            4=>{g.balances.remove(1);},5=>{g.nonnegative.remove(1);},6=>g.demands[0].1=q("2"),
            7=>g.source=1,8=>g.demands[0]=(0,q("0")),_=>{g.demands.clear();},
        }}assert!(check(&s,&t,&bad).is_err(),"attack {attack}");}
        let mut dead=c.clone();dead.blocks[0].steps.push(Step::Drop{ids:vec![0]});assert!(check(&s,&t,&dead).is_err());
    }
    #[test] fn full_target_domains_objective_rows_maps_and_requested_claims_remain_required() {
        let(s,t,c)=fixture();
        for attack in 0..6 {let mut bad=c.clone();let mut output=t.clone();match attack {
            0=>output.vars[3].upper=Some(q("1")),1=>output.vars[4].integer=true,
            2=>output.rows[4].upper=Some(q("-1")),3=>output.objective.constant+=q("1"),
            4=>{if let End::SubflowLift{body,..}=&mut bad.blocks[0].end {if let End::Return{map,..}=&mut body.end{map.pop();}}},
            _=>{if let End::SubflowLift{body,..}=&mut bad.blocks[0].end {if let End::Return{checks,..}=&mut body.end{checks.pop();}}},
        }
        if attack==1 {bad.claims[0].output_integers=true;}
        assert!(check(&s,&output,&bad).is_err(),"attack {attack}");}
        let mut bad=c.clone();bad.claims[0].objective=Objective::NonIncreasing;assert!(verify(&s,&t,&bad,&c.claims,&Limits::default()).is_err());
    }
    #[test] fn siblings_cannot_borrow_extensions_and_affine_inverse_stays_rejected() {
        let(s,t,mut c)=fixture();let left=c.blocks[0].clone();
        let right=if let End::SubflowLift{body,..}=&left.end{(**body).clone()}else{unreachable!()};
        c.blocks[0]=Block{steps:vec![],end:End::Split{expression:Expr::zero(),integer:None,left:Box::new(left),right:Box::new(right)}};
        assert!(check(&s,&t,&c).is_err());
        let(_,_,mut c)=fixture();let mut reverse=c.claims[0].clone();reverse.reverse=true;reverse.projection.clear();c.claims[0].inverse=Some(1);c.claims.push(reverse);c.blocks.push(Block{steps:vec![],end:End::Return{map:(0..3).map(Expr::var).collect(),checks:vec![]}});
        assert!(check(&s,&t,&c).unwrap_err().contains("inverse requires affine"));
    }
    #[test] fn nested_joint_subflows_retain_prefix_and_share_depth_work_budgets() {
        let(s,t,mut c)=fixture();if let End::SubflowLift{witness,body}=&mut c.blocks[0].end {
            let final_body=(**body).clone();*body=Box::new(Block{steps:vec![],end:End::SubflowLift{witness:witness.clone(),body:Box::new(final_body)}});
        }
        let stats=check(&s,&t,&c).unwrap();assert_eq!(stats.subflow_lifts,2);
        assert!(verify(&s,&t,&c,&c.claims,&Limits{work:stats.work-1,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
        assert!(verify(&s,&t,&c,&c.claims,&Limits{depth:2,..Limits::default()}).unwrap_err().starts_with("RESOURCE_LIMIT"));
        assert_eq!(codec::decode_certificate(&codec::encode_certificate(&c).unwrap()).unwrap(),c);
    }
}
