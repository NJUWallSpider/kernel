use kernel_core::{
    codec, compiler, lp,
    model::{Expr, Q, parse_q},
    proof::{
        Block, CasesStep, Certificate, Derivation, DerivationEnd, End, FlowGroup, FlowWitness,
        IntervalWitness, Kind, MenuWitness, Ref, SignedWitness, Step, SubflowGroup, SubflowWitness,
    },
    rpa,
    verify::{Limits, verify},
};
use num_traits::{One, Zero};
use std::{fs, path::Path};

fn q(text: &str) -> Q {
    parse_q(text).unwrap()
}

fn return_block() -> Block {
    Block {
        steps: vec![],
        end: End::Return {
            map: vec![],
            checks: vec![],
        },
    }
}

fn steps() -> Vec<Step> {
    vec![
        Step::Lin {
            id: 0,
            kind: Kind::Le,
            constant: q("1/3"),
            terms: vec![
                (Ref::VarUpper(0), Q::zero()),
                (Ref::VarLower(0), Q::one()),
                (Ref::VarUpper(0), q("2")),
            ],
        },
        Step::Lin {
            id: 1,
            kind: Kind::Eq,
            constant: Q::zero(),
            terms: vec![(Ref::RowEq(0), q("-1"))],
        },
        Step::Lin {
            id: 2,
            kind: Kind::Int,
            constant: Q::zero(),
            terms: vec![(Ref::VarInt(0), Q::one())],
        },
        Step::Round {
            id: 3,
            le: Ref::RowUpper(0),
            integer: Ref::VarInt(0),
        },
        Step::Drop { ids: vec![] },
        Step::EqPair {
            id: 4,
            positive: Ref::RowLower(0),
            negative: Ref::RowUpper(0),
        },
        Step::Cases(Box::new(CasesStep {
            id: 5,
            kind: Kind::Le,
            expression: Expr::var(0),
            split: Expr::zero(),
            integer: Some(Ref::VarInt(0)),
            left: Box::new(Derivation {
                steps: vec![Step::Drop { ids: vec![1] }],
                end: DerivationEnd::Witness(Ref::Local(1)),
            }),
            right: Box::new(Derivation {
                steps: vec![],
                end: DerivationEnd::Absurd(Ref::Exact),
            }),
        })),
        Step::Plotkin {
            id: 6,
            bits: 3,
            distance: 2,
            variables: vec![(0, 1), (1, 3)],
            cliques: vec![Ref::RowUpper(0)],
        },
    ]
}

fn ends() -> Vec<End> {
    let split = || End::Split {
        expression: Expr::var(0),
        integer: Some(Ref::VarInt(0)),
        left: Box::new(return_block()),
        right: Box::new(return_block()),
    };
    let interval = |intervals| End::IntervalLift {
        intervals,
        body: Box::new(return_block()),
    };
    let menu = |menus| End::MenuLift {
        menus,
        body: Box::new(return_block()),
    };
    let signed = |decompositions| End::SignedLift {
        decompositions,
        body: Box::new(return_block()),
    };
    let flow = |witness| End::FlowLift {
        witness,
        body: Box::new(return_block()),
    };
    let subflow = |witness| End::SubflowLift {
        witness,
        body: Box::new(return_block()),
    };
    vec![
        End::Return {
            map: vec![],
            checks: vec![],
        },
        split(),
        End::Absurd {
            fact: Ref::Local(0),
        },
        interval(vec![]),
        interval(vec![IntervalWitness {
            lower: vec![Expr::var(0)],
            upper: vec![Expr::var(1)],
            checks: vec![Ref::Exact],
        }]),
        menu(vec![]),
        menu(vec![MenuWitness {
            maximum_index: 3,
            activation: Expr::var(0),
            index: Expr::var(1),
            checks: vec![Ref::Local(0)],
        }]),
        signed(vec![]),
        signed(vec![SignedWitness {
            capacity: q("1/2"),
            flow: Expr::var(0),
            activation: Expr::var(1),
            checks: vec![Ref::Exact],
        }]),
        flow(FlowWitness {
            nodes: 2,
            arcs: vec![(0, 1)],
            groups: vec![FlowGroup {
                source: 0,
                commodities: vec![(0, q("1/2"))],
                flows: vec![Expr::var(0)],
                nonnegative: vec![Ref::Exact],
                balances: vec![Ref::Local(1)],
            }],
        }),
        subflow(SubflowWitness {
            nodes: 3,
            arcs: vec![(0, 1), (1, 2)],
            groups: vec![SubflowGroup {
                source: 0,
                demands: vec![(0, q("-1/3"))],
                flows: vec![Expr::var(1)],
                nonnegative: vec![Ref::Exact],
                balances: vec![Ref::Local(2)],
            }],
        }),
    ]
}

#[test]
fn documented_assembly_roundtrip_and_certify_both_directions() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../docs/rpx/examples");
    for name in ["redundant", "elimination", "piecewise"] {
        let dir = root.join(name);
        let source = lp::parse_lp(&fs::read_to_string(dir.join("source.lp")).unwrap()).unwrap();
        let target = lp::parse_lp(&fs::read_to_string(dir.join("target.lp")).unwrap()).unwrap();
        let text = fs::read_to_string(dir.join("proof.rpa")).unwrap();
        let certificate = rpa::assemble(&text).unwrap();
        verify(&source, &target, &certificate, &Limits::default()).unwrap();
        let rendered = rpa::disassemble(&certificate).unwrap();
        assert_eq!(rpa::assemble(&rendered).unwrap(), certificate);
        let bytes = codec::encode_certificate(&certificate).unwrap();
        assert_eq!(bytes[4], 11);
        assert_eq!(codec::decode_certificate(&bytes).unwrap(), certificate);
        assert_eq!(
            rpa::assemble(&text.replace('\n', "\r\n")).unwrap(),
            certificate
        );
        assert_eq!(
            rpa::assemble(text.trim_end_matches('\n')).unwrap(),
            certificate
        );
        assert!(rpa::assemble(&text.replacen("RPA 12", "RPA 11", 1)).is_err());
        assert!(rpa::assemble(&text.replacen("RPA 12", "RPA-S 1", 1)).is_err());
    }
}

#[test]
fn planning_has_no_domain_or_objective_switch() {
    let model =
        lp::parse_lp("Minimize\n obj: x\nSubject To\nBounds\n 0 <= x <= 1\nGeneral\n x\nEnd\n")
            .unwrap();
    let plan = compiler::parse_return_plan_json(r#"{"map":[{"constant":"0","terms":[[0,"1"]]}]}"#)
        .unwrap();
    let goals = compiler::plan_return(&model, &model, &plan, &Limits::default()).unwrap();
    assert_eq!(goals.len(), 4);
    assert_eq!(goals[2].kind, Kind::Int);
    assert_eq!(goals[3].kind, Kind::Le);
    for field in ["claim", "inverse_map", "improvement", "compositions"] {
        let mut value = serde_json::json!({"map": []});
        value[field] = serde_json::json!({});
        assert!(compiler::parse_return_plan_json(&value.to_string()).is_err());
    }
}

fn count_block(block: &Block) -> usize {
    block.steps.iter().map(count_step).sum::<usize>() + count_end(&block.end)
}

fn count_derivation(derivation: &Derivation) -> usize {
    derivation.steps.iter().map(count_step).sum::<usize>() + 1
}

fn count_step(step: &Step) -> usize {
    1 + match step {
        Step::Cases(case) => count_derivation(&case.left) + count_derivation(&case.right),
        _ => 0,
    }
}

fn count_end(end: &End) -> usize {
    1 + match end {
        End::Split { left, right, .. } => count_block(left) + count_block(right),
        End::IntervalLift { body, .. }
        | End::MenuLift { body, .. }
        | End::SignedLift { body, .. }
        | End::FlowLift { body, .. }
        | End::SubflowLift { body, .. } => count_block(body),
        _ => 0,
    }
}

#[test]
fn instruction_lines_match_wire_nodes() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../docs/rpx/examples");
    for name in ["redundant", "elimination", "piecewise"] {
        let text = fs::read_to_string(root.join(name).join("proof.rpa")).unwrap();
        let certificate = rpa::assemble(&text).unwrap();
        let rendered = rpa::disassemble(&certificate).unwrap();
        let instructions = rendered
            .lines()
            .filter(|line| {
                let word = line
                    .trim_start()
                    .split(|c: char| c.is_ascii_whitespace() || c == '(')
                    .next()
                    .unwrap_or("");
                matches!(
                    word,
                    "lin.le"
                        | "lin.eq"
                        | "lin.int"
                        | "round"
                        | "drop"
                        | "eqpair"
                        | "cases.le"
                        | "cases.eq"
                        | "cases.int"
                        | "plotkin"
                        | "ret"
                        | "split"
                        | "absurd"
                        | "interval"
                        | "menu"
                        | "signed"
                        | "flow"
                        | "subflow"
                        | "wit"
                )
            })
            .count();
        assert_eq!(
            instructions,
            count_block(&certificate.forward) + count_block(&certificate.reverse),
            "{name}"
        );
    }
}

#[test]
fn all_variants_roundtrip() {
    let steps = steps();
    for end in ends() {
        let block = Block {
            steps: steps.clone(),
            end,
        };
        let certificate = Certificate {
            forward: block.clone(),
            reverse: block,
        };
        let text = rpa::disassemble(&certificate).unwrap();
        assert_eq!(rpa::assemble(&text).unwrap(), certificate, "{text}");
    }
}

#[test]
fn rejects_malformed_assembly() {
    for text in [
        "RPA 11\n{}",
        "RPA-S 1\n",
        "RPA 12\n.forward\n  claim f0\n  ret () ()\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  ret () ()\n  lin.le f0, 0\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  ret () ()\n",
        "RPA 12\n.forward\n.forward\n  ret () ()\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  end\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  wit f0\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  split x0\n  left a1\n    ret () ()\n  right a1\n    ret () ()\n  end\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  ret (x0\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  lin.le f0, x0\n  ret () ()\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  ret (x0*x1) (exact)\n.reverse\n  ret () ()\n",
        "RPA 12\n.forward\n  ret (x0/7) (exact)\n.reverse\n  ret () ()\n",
    ] {
        assert!(rpa::assemble(text).is_err(), "{text}");
    }
}

#[test]
fn large_linear_terms_preserve_order() {
    let step = Step::Lin {
        id: 0,
        kind: Kind::Le,
        constant: Q::zero(),
        terms: vec![
            (Ref::VarUpper(0), Q::zero()),
            (Ref::VarLower(0), Q::one()),
            (Ref::VarUpper(0), q("2")),
        ],
    };
    let block = Block {
        steps: vec![step],
        end: End::Return {
            map: vec![],
            checks: vec![],
        },
    };
    let certificate = Certificate {
        forward: block.clone(),
        reverse: block,
    };
    let text = rpa::disassemble(&certificate).unwrap();
    let line = text
        .lines()
        .find(|line| line.trim_start().starts_with("lin.le"))
        .unwrap();
    let zero = line.find("0*v0.hi").unwrap();
    let lower = line.find("v0.lo").unwrap();
    let twice = line.find("2*v0.hi").unwrap();
    assert!(zero < lower && lower < twice, "{line}");
    assert_eq!(rpa::assemble(&text).unwrap(), certificate);
}
