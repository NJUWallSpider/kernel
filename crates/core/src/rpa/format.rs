//! Deterministic RPA 12 disassembly.
use super::{HEADER, MAX_DEPTH, MAX_SOURCE_BYTES};
use crate::model::{Expr, Q};
use crate::proof::{
    Block, CasesStep, Certificate, Derivation, DerivationEnd, End, FlowGroup, FlowWitness,
    IntervalWitness, Kind, MenuWitness, Ref, SignedWitness, Step, SubflowGroup, SubflowWitness,
};
use num_traits::{One, Signed, Zero};

pub(super) fn render(certificate: &Certificate) -> Result<String, String> {
    let mut builder = Builder::new();
    builder.push(HEADER)?;
    builder.push(".forward\n")?;
    render_block(&certificate.forward, 1, 0, 1, &mut builder)?;
    builder.push("\n.reverse\n")?;
    render_block(&certificate.reverse, 1, 0, 1, &mut builder)?;
    Ok(builder.out)
}

struct Builder {
    out: String,
}

impl Builder {
    fn new() -> Self {
        Self { out: String::new() }
    }

    fn push(&mut self, text: &str) -> Result<(), String> {
        let length = self
            .out
            .len()
            .checked_add(text.len())
            .ok_or_else(|| "RESOURCE_LIMIT RPA output bytes".to_string())?;
        if length > MAX_SOURCE_BYTES {
            return Err("RESOURCE_LIMIT RPA output bytes".into());
        }
        self.out.push_str(text);
        Ok(())
    }

    fn line(&mut self, indent: usize, text: &str) -> Result<(), String> {
        for _ in 0..indent {
            self.push("  ")?;
        }
        self.push(text)?;
        self.push("\n")
    }
}

fn render_block(
    block: &Block,
    indent: usize,
    assumption: usize,
    depth: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    if depth > MAX_DEPTH {
        return Err("RESOURCE_LIMIT RPA depth".into());
    }
    for step in &block.steps {
        render_step(step, indent, assumption, depth, builder)?;
    }
    render_end(&block.end, indent, assumption, depth, builder)
}

fn render_step(
    step: &Step,
    indent: usize,
    assumption: usize,
    depth: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    match step {
        Step::Lin {
            id,
            kind,
            constant,
            terms,
        } => {
            let text = format!(
                "lin.{} f{id}, {}",
                kind_name(*kind),
                render_linear(constant, terms)
            );
            builder.line(indent, &text)
        }
        Step::Round { id, le, integer } => builder.line(
            indent,
            &format!("round f{id}, {}, {}", render_ref(le), render_ref(integer)),
        ),
        Step::Drop { ids } => {
            if ids.is_empty() {
                builder.line(indent, "drop")
            } else {
                let registers = ids
                    .iter()
                    .map(|id| format!("f{id}"))
                    .collect::<Vec<_>>()
                    .join(", ");
                builder.line(indent, &format!("drop {registers}"))
            }
        }
        Step::EqPair {
            id,
            positive,
            negative,
        } => builder.line(
            indent,
            &format!(
                "eqpair f{id}, {}, {}",
                render_ref(positive),
                render_ref(negative)
            ),
        ),
        Step::Cases(case) => render_cases(case, indent, assumption, depth, builder),
        Step::Plotkin {
            id,
            bits,
            distance,
            variables,
            cliques,
        } => builder.line(
            indent,
            &format!(
                "plotkin f{id}, bits={bits}, dist={distance}, vars={}, cliques={}",
                render_coord_labels(variables),
                render_ref_list(cliques)
            ),
        ),
    }
}

fn render_cases(
    case: &CasesStep,
    indent: usize,
    assumption: usize,
    depth: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    let mut header = format!(
        "cases.{} f{}, {}, split {}",
        kind_name(case.kind),
        case.id,
        render_expr(&case.expression),
        render_expr(&case.split)
    );
    if let Some(integer) = &case.integer {
        header.push_str(", int ");
        header.push_str(&render_ref(integer));
    }
    builder.line(indent, &header)?;
    builder.line(indent, &format!("left a{assumption}"))?;
    render_derivation(&case.left, indent + 1, assumption + 1, depth + 1, builder)?;
    builder.line(indent, &format!("right a{assumption}"))?;
    render_derivation(&case.right, indent + 1, assumption + 1, depth + 1, builder)?;
    builder.line(indent, "end")
}

fn render_derivation(
    derivation: &Derivation,
    indent: usize,
    assumption: usize,
    depth: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    if depth > MAX_DEPTH {
        return Err("RESOURCE_LIMIT RPA depth".into());
    }
    for step in &derivation.steps {
        render_step(step, indent, assumption, depth, builder)?;
    }
    match &derivation.end {
        DerivationEnd::Witness(fact) => builder.line(indent, &format!("wit {}", render_ref(fact))),
        DerivationEnd::Absurd(fact) => {
            builder.line(indent, &format!("absurd {}", render_ref(fact)))
        }
    }
}

fn render_end(
    end: &End,
    indent: usize,
    assumption: usize,
    depth: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    match end {
        End::Return { map, checks } => render_ret(map, checks, indent, builder),
        End::Split {
            expression,
            integer,
            left,
            right,
        } => {
            let mut header = format!("split {}", render_expr(expression));
            if let Some(integer) = integer {
                header.push_str(", int ");
                header.push_str(&render_ref(integer));
            }
            builder.line(indent, &header)?;
            builder.line(indent, &format!("left a{assumption}"))?;
            render_block(left, indent + 1, assumption + 1, depth + 1, builder)?;
            builder.line(indent, &format!("right a{assumption}"))?;
            render_block(right, indent + 1, assumption + 1, depth + 1, builder)?;
            builder.line(indent, "end")
        }
        End::Absurd { fact } => builder.line(indent, &format!("absurd {}", render_ref(fact))),
        End::IntervalLift { intervals, body } => {
            builder.line(indent, "interval")?;
            for witness in intervals {
                render_interval_witness(witness, indent + 1, builder)?;
            }
            builder.line(indent, "body")?;
            render_block(body, indent + 1, assumption, depth + 1, builder)?;
            builder.line(indent, "end")
        }
        End::MenuLift { menus, body } => {
            builder.line(indent, "menu")?;
            for witness in menus {
                render_menu_witness(witness, indent + 1, builder)?;
            }
            builder.line(indent, "body")?;
            render_block(body, indent + 1, assumption, depth + 1, builder)?;
            builder.line(indent, "end")
        }
        End::SignedLift {
            decompositions,
            body,
        } => {
            builder.line(indent, "signed")?;
            for witness in decompositions {
                render_signed_witness(witness, indent + 1, builder)?;
            }
            builder.line(indent, "body")?;
            render_block(body, indent + 1, assumption, depth + 1, builder)?;
            builder.line(indent, "end")
        }
        End::FlowLift { witness, body } => {
            render_flow_payload(witness, indent, builder)?;
            builder.line(indent, "body")?;
            render_block(body, indent + 1, assumption, depth + 1, builder)?;
            builder.line(indent, "end")
        }
        End::SubflowLift { witness, body } => {
            render_subflow_payload(witness, indent, builder)?;
            builder.line(indent, "body")?;
            render_block(body, indent + 1, assumption, depth + 1, builder)?;
            builder.line(indent, "end")
        }
    }
}

fn render_interval_witness(
    witness: &IntervalWitness,
    indent: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    builder.line(
        indent,
        &format!(
            "lower {} upper {} checks {}",
            render_expr_list(&witness.lower),
            render_expr_list(&witness.upper),
            render_ref_list(&witness.checks)
        ),
    )
}

fn render_menu_witness(
    witness: &MenuWitness,
    indent: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    builder.line(
        indent,
        &format!(
            "K={} act=({}) idx=({}) checks={}",
            witness.maximum_index,
            render_expr(&witness.activation),
            render_expr(&witness.index),
            render_ref_list(&witness.checks)
        ),
    )
}

fn render_signed_witness(
    witness: &SignedWitness,
    indent: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    builder.line(
        indent,
        &format!(
            "C={} flow=({}) act=({}) checks={}",
            witness.capacity,
            render_expr(&witness.flow),
            render_expr(&witness.activation),
            render_ref_list(&witness.checks)
        ),
    )
}

fn render_flow_payload(
    witness: &FlowWitness,
    indent: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    builder.line(indent, &format!("flow nodes={}", witness.nodes))?;
    for (from, to) in &witness.arcs {
        builder.line(indent + 1, &format!("arc {from}, {to}"))?;
    }
    for group in &witness.groups {
        render_flow_group(group, indent + 1, builder)?;
    }
    Ok(())
}

fn render_flow_group(
    group: &FlowGroup,
    indent: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    builder.line(
        indent,
        &format!(
            "group source={} commodities={} flows={} nonneg={} balance={}",
            group.source,
            render_q_pairs(&group.commodities),
            render_expr_list(&group.flows),
            render_ref_list(&group.nonnegative),
            render_ref_list(&group.balances)
        ),
    )
}

fn render_subflow_payload(
    witness: &SubflowWitness,
    indent: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    builder.line(indent, &format!("subflow nodes={}", witness.nodes))?;
    for (from, to) in &witness.arcs {
        builder.line(indent + 1, &format!("arc {from}, {to}"))?;
    }
    for group in &witness.groups {
        render_subflow_group(group, indent + 1, builder)?;
    }
    Ok(())
}

fn render_subflow_group(
    group: &SubflowGroup,
    indent: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    builder.line(
        indent,
        &format!(
            "group source={} demands={} flows={} nonneg={} balance={}",
            group.source,
            render_q_pairs(&group.demands),
            render_expr_list(&group.flows),
            render_ref_list(&group.nonnegative),
            render_ref_list(&group.balances)
        ),
    )
}

fn render_ret(
    map: &[Expr],
    checks: &[Ref],
    indent: usize,
    builder: &mut Builder,
) -> Result<(), String> {
    let map_items = map.iter().map(render_expr).collect::<Vec<_>>();
    let check_items = checks.iter().map(render_ref).collect::<Vec<_>>();
    let indent_text = "  ".repeat(indent);
    let inline = format!(
        "{indent_text}ret {} {}",
        render_items(&map_items),
        render_items(&check_items)
    );
    if inline.len() <= 100 {
        builder.push(&inline)?;
        return builder.push("\n");
    }

    builder.push(&indent_text)?;
    builder.push("ret ")?;
    if map_items.is_empty() {
        builder.push("() ")?;
    } else {
        builder.push("(\n")?;
        for item in map_items {
            builder.push(&indent_text)?;
            builder.push("  ")?;
            builder.push(&item)?;
            builder.push(",\n")?;
        }
        builder.push(&indent_text)?;
        builder.push(") ")?;
    }
    if check_items.is_empty() {
        builder.push("()\n")
    } else {
        builder.push("(\n")?;
        for item in check_items {
            builder.push(&indent_text)?;
            builder.push("  ")?;
            builder.push(&item)?;
            builder.push(",\n")?;
        }
        builder.push(&indent_text)?;
        builder.push(")\n")
    }
}

fn render_items(items: &[String]) -> String {
    format!("({})", items.join(", "))
}

fn render_expr_list(values: &[Expr]) -> String {
    let items = values.iter().map(render_expr).collect::<Vec<_>>();
    render_items(&items)
}

fn render_ref_list(values: &[Ref]) -> String {
    let items = values.iter().map(render_ref).collect::<Vec<_>>();
    render_items(&items)
}

fn render_coord_labels(values: &[(u32, u64)]) -> String {
    let items = values
        .iter()
        .map(|(id, label)| format!("x{id}:{label}"))
        .collect::<Vec<_>>();
    render_items(&items)
}

fn render_q_pairs(values: &[(u32, Q)]) -> String {
    let items = values
        .iter()
        .map(|(id, value)| format!("{id}:{value}"))
        .collect::<Vec<_>>();
    render_items(&items)
}

fn render_expr(expression: &Expr) -> String {
    let mut out = String::new();
    let mut first = true;
    if !expression.constant.is_zero() || expression.terms.is_empty() {
        push_q_term(&mut out, &expression.constant, None, &mut first);
    }
    for (id, coefficient) in &expression.terms {
        let body = format!("x{id}");
        push_q_term(&mut out, coefficient, Some(&body), &mut first);
    }
    out
}

fn render_linear(constant: &Q, terms: &[(Ref, Q)]) -> String {
    let mut out = String::new();
    let mut first = true;
    if !constant.is_zero() || terms.is_empty() {
        push_q_term(&mut out, constant, None, &mut first);
    }
    for (reference, coefficient) in terms {
        let body = render_ref(reference);
        push_q_term(&mut out, coefficient, Some(&body), &mut first);
    }
    out
}

fn push_q_term(out: &mut String, value: &Q, body: Option<&str>, first: &mut bool) {
    let negative = value.is_negative();
    let magnitude = if negative {
        -value.clone()
    } else {
        value.clone()
    };
    if *first {
        if negative {
            out.push('-');
        }
        *first = false;
    } else if negative {
        out.push_str(" - ");
    } else {
        out.push_str(" + ");
    }
    match body {
        None => out.push_str(&magnitude.to_string()),
        Some(body) => {
            if magnitude.is_one() {
                out.push_str(body);
            } else {
                out.push_str(&magnitude.to_string());
                out.push('*');
                out.push_str(body);
            }
        }
    }
}

fn render_ref(reference: &Ref) -> String {
    match reference {
        Ref::VarLower(id) => format!("v{id}.lo"),
        Ref::VarUpper(id) => format!("v{id}.hi"),
        Ref::VarInt(id) => format!("v{id}.int"),
        Ref::RowLower(id) => format!("r{id}.lo"),
        Ref::RowUpper(id) => format!("r{id}.hi"),
        Ref::RowEq(id) => format!("r{id}.eq"),
        Ref::Local(id) => format!("f{id}"),
        Ref::Assumption(id) => format!("a{id}"),
        Ref::Exact => "exact".into(),
    }
}

fn kind_name(kind: Kind) -> &'static str {
    match kind {
        Kind::Le => "le",
        Kind::Eq => "eq",
        Kind::Int => "int",
    }
}
