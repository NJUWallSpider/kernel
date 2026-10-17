//! Line-oriented RPA 12 parser. It lowers text directly to `Certificate`.
use super::{MAX_DEPTH, MAX_NODES, MAX_SOURCE_BYTES};
use crate::model::{Expr, Q, parse_q};
use crate::proof::{
    Block, CasesStep, Certificate, Derivation, DerivationEnd, End, FlowGroup, FlowWitness,
    IntervalWitness, Kind, MenuWitness, Ref, SignedWitness, Step, SubflowGroup, SubflowWitness,
};
use num_traits::{One, Zero};
use std::fmt::Display;

struct LogicalLine {
    number: usize,
    text: String,
}

pub(super) fn parse(text: &str) -> Result<Certificate, String> {
    if text.len() > MAX_SOURCE_BYTES {
        return Err("RESOURCE_LIMIT RPA bytes".into());
    }
    let mut physical = text.split('\n');
    let first = physical.next().unwrap_or("");
    let first = first.strip_suffix('\r').unwrap_or(first);
    if first != "RPA 12" {
        return Err("INVALID RPA version/header: expected RPA 12".into());
    }

    let mut lines = Vec::new();
    let mut current: Option<(usize, String, i32)> = None;
    for (index, raw) in physical.enumerate() {
        let number = index + 2;
        let raw = raw.strip_suffix('\r').unwrap_or(raw);
        let content = strip_comment(raw).trim();
        if content.is_empty() {
            continue;
        }
        match current.as_mut() {
            Some((start, accumulated, balance)) => {
                *balance =
                    paren_delta(content, *balance).map_err(|detail| line_error(*start, detail))?;
                accumulated.push(' ');
                accumulated.push_str(content);
                if *balance == 0 {
                    let (start, accumulated, _) = current.take().unwrap();
                    lines.push(LogicalLine {
                        number: start,
                        text: accumulated,
                    });
                }
            }
            None => {
                let balance =
                    paren_delta(content, 0).map_err(|detail| line_error(number, detail))?;
                if balance == 0 {
                    lines.push(LogicalLine {
                        number,
                        text: content.to_string(),
                    });
                } else {
                    current = Some((number, content.to_string(), balance));
                }
            }
        }
    }
    if let Some((start, _, _)) = current {
        return Err(line_error(start, "unterminated parenthesized instruction"));
    }

    Parser {
        lines,
        at: 0,
        nodes: 0,
    }
    .document()
}

fn strip_comment(line: &str) -> &str {
    match line.find(';') {
        Some(index) => &line[..index],
        None => line,
    }
}

fn paren_delta(text: &str, mut balance: i32) -> Result<i32, String> {
    for byte in text.bytes() {
        match byte {
            b'(' => balance += 1,
            b')' => {
                balance -= 1;
                if balance < 0 {
                    return Err("unbalanced `)`".into());
                }
            }
            _ => {}
        }
    }
    Ok(balance)
}

fn line_error(number: usize, detail: impl Display) -> String {
    let detail = detail.to_string();
    if detail.starts_with("RESOURCE_LIMIT") {
        detail
    } else {
        format!("INVALID RPA line {number}: {detail}")
    }
}

fn charge_nodes(nodes: &mut usize, count: usize) -> Result<(), String> {
    *nodes = nodes
        .checked_add(count)
        .ok_or_else(|| "RESOURCE_LIMIT RPA nodes".to_string())?;
    if *nodes > MAX_NODES {
        return Err("RESOURCE_LIMIT RPA nodes".into());
    }
    Ok(())
}

fn leading_word(text: &str) -> &str {
    let end = text
        .find(|c: char| c.is_ascii_whitespace() || c == '(')
        .unwrap_or(text.len());
    &text[..end]
}

fn starts_word(text: &str, word: &str) -> bool {
    let Some(rest) = text.strip_prefix(word) else {
        return false;
    };
    rest.is_empty()
        || rest
            .chars()
            .next()
            .is_some_and(|c| c.is_ascii_whitespace() || c == '(')
}

fn starts_field(text: &str, field: &str) -> bool {
    text.strip_prefix(field)
        .is_some_and(|rest| rest.trim_start().starts_with('='))
}

fn is_terminal(text: &str) -> bool {
    [
        "ret", "split", "absurd", "interval", "menu", "signed", "flow", "subflow",
    ]
    .iter()
    .any(|word| starts_word(text, word))
}

fn is_step(text: &str) -> bool {
    [
        "lin.le",
        "lin.eq",
        "lin.int",
        "round",
        "drop",
        "eqpair",
        "cases.le",
        "cases.eq",
        "cases.int",
        "plotkin",
    ]
    .iter()
    .any(|word| starts_word(text, word))
}

struct Parser {
    lines: Vec<LogicalLine>,
    at: usize,
    nodes: usize,
}

impl Parser {
    fn document(mut self) -> Result<Certificate, String> {
        if self.lines.is_empty() || self.lines[0].text != ".forward" {
            return Err("INVALID RPA: missing .forward".into());
        }
        self.at = 1;
        let forward = self.block(0, 1)?;
        if self.at == self.lines.len() {
            return Err("INVALID RPA: missing .reverse".into());
        }
        if self.lines[self.at].text == ".forward" {
            return Err("INVALID RPA: duplicate .forward".into());
        }
        if self.lines[self.at].text != ".reverse" {
            let number = self.lines[self.at].number;
            return Err(line_error(
                number,
                format!("expected .reverse, found `{}`", self.lines[self.at].text),
            ));
        }
        self.at += 1;
        let reverse = self.block(0, 1)?;
        if self.at < self.lines.len() {
            let number = self.lines[self.at].number;
            let text = &self.lines[self.at].text;
            if text == ".forward" {
                return Err("INVALID RPA: duplicate .forward".into());
            }
            if text == ".reverse" {
                return Err("INVALID RPA: duplicate .reverse".into());
            }
            return Err(line_error(
                number,
                format!("unexpected content after .reverse block: `{text}`"),
            ));
        }
        Ok(Certificate { forward, reverse })
    }

    fn current(&self) -> Option<&LogicalLine> {
        self.lines.get(self.at)
    }

    fn eof_error(&self, detail: impl Display) -> String {
        let number = self
            .lines
            .last()
            .map_or(1, |line| line.number.saturating_add(1));
        line_error(number, detail)
    }

    fn block(&mut self, assumption: usize, nest: usize) -> Result<Block, String> {
        if nest > MAX_DEPTH {
            return Err("RESOURCE_LIMIT RPA depth".into());
        }
        let mut steps = Vec::new();
        loop {
            let Some(line) = self.current() else {
                return Err(self.eof_error("missing terminal"));
            };
            let number = line.number;
            let text = line.text.as_str();
            if text == ".forward" {
                return Err("INVALID RPA: duplicate .forward".into());
            }
            if text == ".reverse" {
                return Err(line_error(number, "missing terminal before .reverse"));
            }
            if text == "end"
                || text == "body"
                || starts_word(text, "left")
                || starts_word(text, "right")
            {
                return Err(line_error(
                    number,
                    format!("unexpected `{text}` while expecting a terminal"),
                ));
            }
            if is_terminal(text) {
                charge_nodes(&mut self.nodes, 1)?;
                let end = self.terminal(assumption, nest)?;
                return Ok(Block { steps, end });
            }
            if starts_word(text, "wit") {
                return Err(line_error(
                    number,
                    "wit is only valid as a cases derivation end",
                ));
            }
            if !is_step(text) {
                return Err(line_error(
                    number,
                    format!("unknown instruction `{}`", leading_word(text)),
                ));
            }
            charge_nodes(&mut self.nodes, 1)?;
            steps.push(self.step(assumption, nest)?);
        }
    }

    fn step(&mut self, assumption: usize, nest: usize) -> Result<Step, String> {
        let number = self.current().map(|line| line.number).unwrap();
        if starts_word(&self.lines[self.at].text, "cases.le")
            || starts_word(&self.lines[self.at].text, "cases.eq")
            || starts_word(&self.lines[self.at].text, "cases.int")
        {
            return self.cases_step(assumption, nest);
        }
        let result = {
            let text = self.lines[self.at].text.as_str();
            let mut cursor = Cursor::new(text, &mut self.nodes);
            let word = cursor.word()?;
            match word {
                "lin.le" => {
                    let id = cursor.dest()?;
                    cursor.comma()?;
                    let (constant, terms) = cursor.linear()?;
                    cursor.eof()?;
                    Ok(Step::Lin {
                        id,
                        kind: Kind::Le,
                        constant,
                        terms,
                    })
                }
                "lin.eq" => {
                    let id = cursor.dest()?;
                    cursor.comma()?;
                    let (constant, terms) = cursor.linear()?;
                    cursor.eof()?;
                    Ok(Step::Lin {
                        id,
                        kind: Kind::Eq,
                        constant,
                        terms,
                    })
                }
                "lin.int" => {
                    let id = cursor.dest()?;
                    cursor.comma()?;
                    let (constant, terms) = cursor.linear()?;
                    cursor.eof()?;
                    Ok(Step::Lin {
                        id,
                        kind: Kind::Int,
                        constant,
                        terms,
                    })
                }
                "round" => {
                    let id = cursor.dest()?;
                    cursor.comma()?;
                    let le = cursor.reference()?;
                    cursor.comma()?;
                    let integer = cursor.reference()?;
                    cursor.eof()?;
                    Ok(Step::Round { id, le, integer })
                }
                "drop" => {
                    let mut ids = Vec::new();
                    cursor.skip_ws();
                    if !cursor.eof_now() {
                        loop {
                            ids.push(cursor.dest()?);
                            if !cursor.comma_if()? {
                                break;
                            }
                        }
                    }
                    cursor.eof()?;
                    Ok(Step::Drop { ids })
                }
                "eqpair" => {
                    let id = cursor.dest()?;
                    cursor.comma()?;
                    let positive = cursor.reference()?;
                    cursor.comma()?;
                    let negative = cursor.reference()?;
                    cursor.eof()?;
                    Ok(Step::EqPair {
                        id,
                        positive,
                        negative,
                    })
                }
                "plotkin" => {
                    let id = cursor.dest()?;
                    cursor.comma()?;
                    let bits = cursor.field_u32("bits")?;
                    cursor.comma()?;
                    let distance = cursor.field_u32("dist")?;
                    cursor.comma()?;
                    let variables = cursor.field_coord_labels("vars")?;
                    cursor.comma()?;
                    let cliques = cursor.field_refs("cliques")?;
                    cursor.eof()?;
                    Ok(Step::Plotkin {
                        id,
                        bits,
                        distance,
                        variables,
                        cliques,
                    })
                }
                other => Err(format!("unknown step `{other}`")),
            }
        };
        let step = result.map_err(|detail| line_error(number, detail))?;
        self.at += 1;
        Ok(step)
    }

    fn cases_step(&mut self, assumption: usize, nest: usize) -> Result<Step, String> {
        let number = self.current().map(|line| line.number).unwrap();
        let result: Result<(u32, Kind, Expr, Expr, Option<Ref>), String> = {
            let text = self.lines[self.at].text.as_str();
            let mut cursor = Cursor::new(text, &mut self.nodes);
            let word = cursor.word()?;
            let kind = match word {
                "cases.le" => Kind::Le,
                "cases.eq" => Kind::Eq,
                "cases.int" => Kind::Int,
                other => return Err(line_error(number, format!("unknown cases step `{other}`"))),
            };
            let id = cursor.dest()?;
            cursor.comma()?;
            let expression = cursor.expr()?;
            cursor.comma()?;
            cursor.expect_ident("split")?;
            let split = cursor.expr()?;
            let integer = cursor.optional_integer()?;
            cursor.eof()?;
            Ok((id, kind, expression, split, integer))
        };
        let (id, kind, expression, split, integer) =
            result.map_err(|detail| line_error(number, detail))?;
        self.at += 1;
        self.header("left", assumption)?;
        let left = self.derivation(assumption + 1, nest + 1)?;
        self.header("right", assumption)?;
        let right = self.derivation(assumption + 1, nest + 1)?;
        self.expect_exact("end")?;
        Ok(Step::Cases(Box::new(CasesStep {
            id,
            kind,
            expression,
            split,
            integer,
            left: Box::new(left),
            right: Box::new(right),
        })))
    }

    fn terminal(&mut self, assumption: usize, nest: usize) -> Result<End, String> {
        let text = self.lines[self.at].text.as_str();
        if starts_word(text, "ret") {
            let number = self.lines[self.at].number;
            let result: Result<End, String> = {
                let mut cursor = Cursor::new(text, &mut self.nodes);
                let word = cursor.word()?;
                if word != "ret" {
                    return Err(line_error(number, format!("expected ret, found `{word}`")));
                }
                let map = cursor.expr_list()?;
                let checks = cursor.ref_list()?;
                cursor.eof()?;
                Ok(End::Return { map, checks })
            };
            let end = result.map_err(|detail| line_error(number, detail))?;
            self.at += 1;
            return Ok(end);
        }
        if starts_word(text, "split") {
            let number = self.lines[self.at].number;
            let result: Result<(Expr, Option<Ref>), String> = {
                let mut cursor = Cursor::new(text, &mut self.nodes);
                cursor.word()?;
                let expression = cursor.expr()?;
                let integer = cursor.optional_integer()?;
                cursor.eof()?;
                Ok((expression, integer))
            };
            let (expression, integer) = result.map_err(|detail| line_error(number, detail))?;
            self.at += 1;
            self.header("left", assumption)?;
            let left = self.block(assumption + 1, nest + 1)?;
            self.header("right", assumption)?;
            let right = self.block(assumption + 1, nest + 1)?;
            self.expect_exact("end")?;
            return Ok(End::Split {
                expression,
                integer,
                left: Box::new(left),
                right: Box::new(right),
            });
        }
        if starts_word(text, "absurd") {
            let number = self.lines[self.at].number;
            let result: Result<End, String> = {
                let mut cursor = Cursor::new(text, &mut self.nodes);
                cursor.word()?;
                let fact = cursor.reference()?;
                cursor.eof()?;
                Ok(End::Absurd { fact })
            };
            let end = result.map_err(|detail| line_error(number, detail))?;
            self.at += 1;
            return Ok(end);
        }
        if starts_word(text, "interval") {
            return self.interval_lift(assumption, nest);
        }
        if starts_word(text, "menu") {
            return self.menu_lift(assumption, nest);
        }
        if starts_word(text, "signed") {
            return self.signed_lift(assumption, nest);
        }
        if starts_word(text, "flow") {
            return self.flow_lift(assumption, nest, false);
        }
        if starts_word(text, "subflow") {
            return self.flow_lift(assumption, nest, true);
        }
        Err(line_error(
            self.lines[self.at].number,
            format!("unknown terminal `{}`", leading_word(text)),
        ))
    }

    fn derivation(&mut self, assumption: usize, nest: usize) -> Result<Derivation, String> {
        if nest > MAX_DEPTH {
            return Err("RESOURCE_LIMIT RPA depth".into());
        }
        let mut steps = Vec::new();
        loop {
            if self.at == self.lines.len() {
                return Err(self.eof_error("missing wit or absurd derivation end"));
            }
            let number = self.lines[self.at].number;
            let text = self.lines[self.at].text.as_str();
            if starts_word(text, "wit") {
                let result: Result<DerivationEnd, String> = {
                    let mut cursor = Cursor::new(text, &mut self.nodes);
                    cursor.word()?;
                    let fact = cursor.reference()?;
                    cursor.eof()?;
                    Ok(DerivationEnd::Witness(fact))
                };
                let end = result.map_err(|detail| line_error(number, detail))?;
                charge_nodes(&mut self.nodes, 1)?;
                self.at += 1;
                return Ok(Derivation { steps, end });
            }
            if starts_word(text, "absurd") {
                let result: Result<DerivationEnd, String> = {
                    let mut cursor = Cursor::new(text, &mut self.nodes);
                    cursor.word()?;
                    let fact = cursor.reference()?;
                    cursor.eof()?;
                    Ok(DerivationEnd::Absurd(fact))
                };
                let end = result.map_err(|detail| line_error(number, detail))?;
                charge_nodes(&mut self.nodes, 1)?;
                self.at += 1;
                return Ok(Derivation { steps, end });
            }
            if text == "end"
                || text == "body"
                || starts_word(text, "left")
                || starts_word(text, "right")
            {
                return Err(line_error(
                    number,
                    format!("unexpected `{text}` while expecting a derivation"),
                ));
            }
            if !is_step(text) {
                return Err(line_error(
                    number,
                    format!(
                        "expected a step or derivation end, found `{}`",
                        leading_word(text)
                    ),
                ));
            }
            charge_nodes(&mut self.nodes, 1)?;
            steps.push(self.step(assumption, nest)?);
        }
    }

    fn interval_lift(&mut self, assumption: usize, nest: usize) -> Result<End, String> {
        let number = self.lines[self.at].number;
        let result: Result<(), String> = {
            let text = self.lines[self.at].text.as_str();
            let mut cursor = Cursor::new(text, &mut self.nodes);
            cursor.word()?;
            cursor.eof()?;
            Ok(())
        };
        result.map_err(|detail| line_error(number, detail))?;
        self.at += 1;
        let mut intervals = Vec::new();
        while self.at < self.lines.len() {
            if !starts_word(&self.lines[self.at].text, "lower") {
                break;
            }
            let number = self.lines[self.at].number;
            let result: Result<IntervalWitness, String> = {
                let text = self.lines[self.at].text.as_str();
                let mut cursor = Cursor::new(text, &mut self.nodes);
                cursor.word()?;
                let lower = cursor.expr_list()?;
                cursor.expect_ident("upper")?;
                let upper = cursor.expr_list()?;
                cursor.expect_ident("checks")?;
                let checks = cursor.ref_list()?;
                cursor.eof()?;
                Ok(IntervalWitness {
                    lower,
                    upper,
                    checks,
                })
            };
            intervals.push(result.map_err(|detail| line_error(number, detail))?);
            self.at += 1;
        }
        self.expect_exact("body")?;
        let body = self.block(assumption, nest + 1)?;
        self.expect_exact("end")?;
        Ok(End::IntervalLift {
            intervals,
            body: Box::new(body),
        })
    }

    fn menu_lift(&mut self, assumption: usize, nest: usize) -> Result<End, String> {
        let number = self.lines[self.at].number;
        let result: Result<(), String> = {
            let text = self.lines[self.at].text.as_str();
            let mut cursor = Cursor::new(text, &mut self.nodes);
            cursor.word()?;
            cursor.eof()?;
            Ok(())
        };
        result.map_err(|detail| line_error(number, detail))?;
        self.at += 1;
        let mut menus = Vec::new();
        while self.at < self.lines.len() {
            if !starts_field(&self.lines[self.at].text, "K") {
                break;
            }
            let number = self.lines[self.at].number;
            let result: Result<MenuWitness, String> = {
                let text = self.lines[self.at].text.as_str();
                let mut cursor = Cursor::new(text, &mut self.nodes);
                let maximum_index = cursor.field_u32("K")?;
                let activation = cursor.field_expr("act")?;
                let index = cursor.field_expr("idx")?;
                let checks = cursor.field_refs("checks")?;
                cursor.eof()?;
                Ok(MenuWitness {
                    maximum_index,
                    activation,
                    index,
                    checks,
                })
            };
            menus.push(result.map_err(|detail| line_error(number, detail))?);
            self.at += 1;
        }
        self.expect_exact("body")?;
        let body = self.block(assumption, nest + 1)?;
        self.expect_exact("end")?;
        Ok(End::MenuLift {
            menus,
            body: Box::new(body),
        })
    }

    fn signed_lift(&mut self, assumption: usize, nest: usize) -> Result<End, String> {
        let number = self.lines[self.at].number;
        let result: Result<(), String> = {
            let text = self.lines[self.at].text.as_str();
            let mut cursor = Cursor::new(text, &mut self.nodes);
            cursor.word()?;
            cursor.eof()?;
            Ok(())
        };
        result.map_err(|detail| line_error(number, detail))?;
        self.at += 1;
        let mut decompositions = Vec::new();
        while self.at < self.lines.len() {
            if !starts_field(&self.lines[self.at].text, "C") {
                break;
            }
            let number = self.lines[self.at].number;
            let result: Result<SignedWitness, String> = {
                let text = self.lines[self.at].text.as_str();
                let mut cursor = Cursor::new(text, &mut self.nodes);
                let capacity = cursor.field_signed_q("C")?;
                let flow = cursor.field_expr("flow")?;
                let activation = cursor.field_expr("act")?;
                let checks = cursor.field_refs("checks")?;
                cursor.eof()?;
                Ok(SignedWitness {
                    capacity,
                    flow,
                    activation,
                    checks,
                })
            };
            decompositions.push(result.map_err(|detail| line_error(number, detail))?);
            self.at += 1;
        }
        self.expect_exact("body")?;
        let body = self.block(assumption, nest + 1)?;
        self.expect_exact("end")?;
        Ok(End::SignedLift {
            decompositions,
            body: Box::new(body),
        })
    }

    fn flow_lift(&mut self, assumption: usize, nest: usize, subflow: bool) -> Result<End, String> {
        let number = self.lines[self.at].number;
        let result: Result<u32, String> = {
            let text = self.lines[self.at].text.as_str();
            let mut cursor = Cursor::new(text, &mut self.nodes);
            cursor.word()?;
            let nodes = cursor.field_u32("nodes")?;
            cursor.eof()?;
            Ok(nodes)
        };
        let nodes = result.map_err(|detail| line_error(number, detail))?;
        self.at += 1;
        let mut arcs: Vec<(u32, u32)> = Vec::new();
        let mut groups = Vec::new();
        let mut seen_group = false;
        loop {
            if self.at == self.lines.len() {
                return Err(self.eof_error("missing body in flow lift"));
            }
            let number = self.lines[self.at].number;
            let text = self.lines[self.at].text.as_str();
            if text == "body" {
                break;
            }
            if starts_word(text, "arc") {
                if seen_group {
                    return Err(line_error(number, "arc lines must precede group lines"));
                }
                let result: Result<(u32, u32), String> = {
                    let mut cursor = Cursor::new(text, &mut self.nodes);
                    cursor.word()?;
                    let from = cursor.u32()?;
                    cursor.comma()?;
                    let to = cursor.u32()?;
                    cursor.eof()?;
                    Ok((from, to))
                };
                arcs.push(result.map_err(|detail| line_error(number, detail))?);
            } else if starts_word(text, "group") {
                seen_group = true;
                if subflow {
                    let result: Result<SubflowGroup, String> = {
                        let mut cursor = Cursor::new(text, &mut self.nodes);
                        cursor.word()?;
                        let source = cursor.field_u32("source")?;
                        let demands = cursor.field_q_pairs("demands")?;
                        let flows = cursor.field_exprs("flows")?;
                        let nonnegative = cursor.field_refs("nonneg")?;
                        let balances = cursor.field_refs("balance")?;
                        cursor.eof()?;
                        Ok(SubflowGroup {
                            source,
                            demands,
                            flows,
                            nonnegative,
                            balances,
                        })
                    };
                    groups.push(FlowGroupEntry::Sub(
                        result.map_err(|detail| line_error(number, detail))?,
                    ));
                } else {
                    let result: Result<FlowGroup, String> = {
                        let mut cursor = Cursor::new(text, &mut self.nodes);
                        cursor.word()?;
                        let source = cursor.field_u32("source")?;
                        let commodities = cursor.field_q_pairs("commodities")?;
                        let flows = cursor.field_exprs("flows")?;
                        let nonnegative = cursor.field_refs("nonneg")?;
                        let balances = cursor.field_refs("balance")?;
                        cursor.eof()?;
                        Ok(FlowGroup {
                            source,
                            commodities,
                            flows,
                            nonnegative,
                            balances,
                        })
                    };
                    groups.push(FlowGroupEntry::Flow(
                        result.map_err(|detail| line_error(number, detail))?,
                    ));
                }
            } else {
                return Err(line_error(
                    number,
                    format!("unexpected `{text}` in flow payload"),
                ));
            }
            self.at += 1;
        }
        self.expect_exact("body")?;
        let body = self.block(assumption, nest + 1)?;
        self.expect_exact("end")?;
        if subflow {
            let groups = groups
                .into_iter()
                .map(|entry| match entry {
                    FlowGroupEntry::Sub(group) => Ok(group),
                    FlowGroupEntry::Flow(_) => Err("internal flow group mismatch".to_string()),
                })
                .collect::<Result<Vec<_>, _>>()?;
            Ok(End::SubflowLift {
                witness: SubflowWitness {
                    nodes,
                    arcs,
                    groups,
                },
                body: Box::new(body),
            })
        } else {
            let groups = groups
                .into_iter()
                .map(|entry| match entry {
                    FlowGroupEntry::Flow(group) => Ok(group),
                    FlowGroupEntry::Sub(_) => Err("internal flow group mismatch".to_string()),
                })
                .collect::<Result<Vec<_>, _>>()?;
            Ok(End::FlowLift {
                witness: FlowWitness {
                    nodes,
                    arcs,
                    groups,
                },
                body: Box::new(body),
            })
        }
    }

    fn header(&mut self, keyword: &str, expected: usize) -> Result<(), String> {
        if self.at == self.lines.len() {
            return Err(self.eof_error(format!("missing {keyword} a{expected}")));
        }
        let number = self.lines[self.at].number;
        let result: Result<u32, String> = {
            let text = self.lines[self.at].text.as_str();
            let mut cursor = Cursor::new(text, &mut self.nodes);
            let word = cursor.word()?;
            if word != keyword {
                return Err(line_error(
                    number,
                    format!("expected {keyword} a{expected}, found `{word}`"),
                ));
            }
            cursor.skip_ws();
            cursor.expect_char('a')?;
            let index = cursor.u32()?;
            cursor.eof()?;
            Ok(index)
        };
        let index = result.map_err(|detail| line_error(number, detail))?;
        if index as usize != expected {
            return Err(line_error(
                number,
                format!("bad assumption header a{index}, expected a{expected}"),
            ));
        }
        self.at += 1;
        Ok(())
    }

    fn expect_exact(&mut self, expected: &str) -> Result<(), String> {
        let Some(line) = self.current() else {
            return Err(self.eof_error(format!("missing `{expected}`")));
        };
        if line.text != expected {
            return Err(line_error(
                line.number,
                format!("expected `{expected}`, found `{}`", line.text),
            ));
        }
        self.at += 1;
        Ok(())
    }
}

enum FlowGroupEntry {
    Flow(FlowGroup),
    Sub(SubflowGroup),
}

struct Cursor<'a> {
    text: &'a str,
    at: usize,
    nodes: &'a mut usize,
}

impl<'a> Cursor<'a> {
    fn new(text: &'a str, nodes: &'a mut usize) -> Self {
        Self { text, at: 0, nodes }
    }

    fn skip_ws(&mut self) {
        while self
            .text
            .as_bytes()
            .get(self.at)
            .is_some_and(|byte| byte.is_ascii_whitespace())
        {
            self.at += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.text.as_bytes().get(self.at).copied()
    }

    fn eof_now(&mut self) -> bool {
        self.skip_ws();
        self.at == self.text.len()
    }

    fn eof(&mut self) -> Result<(), String> {
        self.skip_ws();
        if self.at == self.text.len() {
            Ok(())
        } else {
            Err(format!("unexpected `{}`", &self.text[self.at..]))
        }
    }

    fn expect_char(&mut self, expected: char) -> Result<(), String> {
        self.skip_ws();
        if self.peek() == Some(expected as u8) {
            self.at += 1;
            Ok(())
        } else {
            Err(format!("expected `{expected}`"))
        }
    }

    fn eat_char(&mut self, expected: char) -> Result<bool, String> {
        self.skip_ws();
        if self.peek() == Some(expected as u8) {
            self.at += 1;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    fn comma(&mut self) -> Result<(), String> {
        self.expect_char(',')
    }

    fn comma_if(&mut self) -> Result<bool, String> {
        self.eat_char(',')
    }

    fn word(&mut self) -> Result<&'a str, String> {
        self.skip_ws();
        let start = self.at;
        while self
            .text
            .as_bytes()
            .get(self.at)
            .is_some_and(|byte| byte.is_ascii_alphanumeric() || *byte == b'.' || *byte == b'_')
        {
            self.at += 1;
        }
        if start == self.at {
            return Err("expected a keyword".into());
        }
        Ok(&self.text[start..self.at])
    }

    fn ident(&mut self) -> Result<&'a str, String> {
        self.skip_ws();
        let start = self.at;
        while self
            .text
            .as_bytes()
            .get(self.at)
            .is_some_and(|byte| byte.is_ascii_alphanumeric() || *byte == b'_')
        {
            self.at += 1;
        }
        if start == self.at {
            return Err("expected a field name".into());
        }
        Ok(&self.text[start..self.at])
    }

    fn expect_ident(&mut self, expected: &str) -> Result<(), String> {
        let found = self.ident()?;
        if found == expected {
            Ok(())
        } else {
            Err(format!("expected `{expected}`, found `{found}`"))
        }
    }

    fn u32(&mut self) -> Result<u32, String> {
        self.skip_ws();
        let start = self.at;
        while self
            .text
            .as_bytes()
            .get(self.at)
            .is_some_and(u8::is_ascii_digit)
        {
            self.at += 1;
        }
        if start == self.at {
            return Err("expected a nonnegative integer".into());
        }
        let value = self.text[start..self.at]
            .parse::<u32>()
            .map_err(|_| "integer out of range".to_string())?;
        Ok(value)
    }

    fn u64(&mut self) -> Result<u64, String> {
        self.skip_ws();
        let start = self.at;
        while self
            .text
            .as_bytes()
            .get(self.at)
            .is_some_and(u8::is_ascii_digit)
        {
            self.at += 1;
        }
        if start == self.at {
            return Err("expected a nonnegative integer".into());
        }
        self.text[start..self.at]
            .parse::<u64>()
            .map_err(|_| "integer out of range".to_string())
    }

    fn dest(&mut self) -> Result<u32, String> {
        self.skip_ws();
        if self.peek() != Some(b'f') {
            return Err("expected register fN".into());
        }
        self.at += 1;
        self.u32()
    }

    fn coord(&mut self) -> Result<u32, String> {
        self.skip_ws();
        if self.peek() != Some(b'x') {
            return Err("expected coordinate xN".into());
        }
        self.at += 1;
        self.u32()
    }

    fn reference(&mut self) -> Result<Ref, String> {
        self.skip_ws();
        if self.text[self.at..].starts_with("exact")
            && self
                .text
                .as_bytes()
                .get(self.at + 5)
                .is_none_or(|byte| !byte.is_ascii_alphanumeric() && *byte != b'_' && *byte != b'.')
        {
            self.at += 5;
            return Ok(Ref::Exact);
        }
        let prefix = self
            .peek()
            .ok_or_else(|| "expected a reference".to_string())?;
        self.at += 1;
        let id = self.u32()?;
        match prefix {
            b'v' => {
                self.expect_char('.')?;
                let side = self.ident()?;
                match side {
                    "lo" => Ok(Ref::VarLower(id)),
                    "hi" => Ok(Ref::VarUpper(id)),
                    "int" => Ok(Ref::VarInt(id)),
                    _ => Err(format!("unknown variable side `{side}`")),
                }
            }
            b'r' => {
                self.expect_char('.')?;
                let side = self.ident()?;
                match side {
                    "lo" => Ok(Ref::RowLower(id)),
                    "hi" => Ok(Ref::RowUpper(id)),
                    "eq" => Ok(Ref::RowEq(id)),
                    _ => Err(format!("unknown row side `{side}`")),
                }
            }
            b'f' => Ok(Ref::Local(id)),
            b'a' => Ok(Ref::Assumption(id)),
            _ => Err(format!("unknown reference prefix `{}`", prefix as char)),
        }
    }

    fn rational(&mut self) -> Result<Q, String> {
        self.skip_ws();
        let start = self.at;
        while self
            .text
            .as_bytes()
            .get(self.at)
            .is_some_and(u8::is_ascii_digit)
        {
            self.at += 1;
        }
        if start == self.at {
            return Err("expected a rational".into());
        }
        if self.peek() == Some(b'/') {
            self.at += 1;
            let denominator = self.at;
            while self
                .text
                .as_bytes()
                .get(self.at)
                .is_some_and(u8::is_ascii_digit)
            {
                self.at += 1;
            }
            if denominator == self.at {
                return Err("expected a rational denominator".into());
            }
        }
        let text = &self.text[start..self.at];
        parse_q(text).map_err(|error| {
            if error.starts_with("RESOURCE_LIMIT") {
                error
            } else {
                format!("invalid rational `{text}`: {error}")
            }
        })
    }

    fn signed_q(&mut self) -> Result<Q, String> {
        self.skip_ws();
        let negative = if self.peek() == Some(b'-') {
            self.at += 1;
            true
        } else {
            if self.peek() == Some(b'+') {
                self.at += 1;
            }
            false
        };
        let value = self.rational()?;
        Ok(if negative { -value } else { value })
    }

    fn charge(&mut self, count: usize) -> Result<(), String> {
        charge_nodes(self.nodes, count)
    }

    fn linear(&mut self) -> Result<(Q, Vec<(Ref, Q)>), String> {
        let mut constant = Q::zero();
        let mut terms = Vec::new();
        let mut sign = if self.eat_char('-')? {
            -1
        } else {
            self.eat_char('+')?;
            1
        };
        loop {
            self.skip_ws();
            if self.peek().is_some_and(|byte| byte.is_ascii_digit()) {
                let coefficient = self.rational()?;
                if self.eat_char('*')? {
                    let reference = self.reference()?;
                    let coefficient = if sign < 0 { -coefficient } else { coefficient };
                    self.charge(1)?;
                    terms.push((reference, coefficient));
                } else {
                    let coefficient = if sign < 0 { -coefficient } else { coefficient };
                    self.charge(1)?;
                    constant += coefficient;
                }
            } else {
                let reference = self.reference()?;
                let coefficient = if sign < 0 { -Q::one() } else { Q::one() };
                self.charge(1)?;
                terms.push((reference, coefficient));
            }
            if self.eat_char('+')? {
                sign = 1;
            } else if self.eat_char('-')? {
                sign = -1;
            } else {
                break;
            }
        }
        Ok((constant, terms))
    }

    fn expr(&mut self) -> Result<Expr, String> {
        self.expr_depth(0)
    }

    fn expr_depth(&mut self, depth: usize) -> Result<Expr, String> {
        if depth > MAX_DEPTH {
            return Err("RESOURCE_LIMIT RPA depth".into());
        }
        let mut constant = Q::zero();
        let mut terms: Vec<(u32, Q)> = Vec::new();
        let mut sign = if self.eat_char('-')? {
            -1
        } else {
            self.eat_char('+')?;
            1
        };
        loop {
            self.skip_ws();
            let factor = if self.peek().is_some_and(|byte| byte.is_ascii_digit()) {
                let coefficient = self.rational()?;
                if self.eat_char('*')? {
                    (Some(coefficient), self.factor(depth)?)
                } else {
                    (
                        None,
                        Expr {
                            constant: coefficient,
                            terms: Vec::new(),
                        },
                    )
                }
            } else {
                (None, self.factor(depth)?)
            };
            let coefficient = factor.0.unwrap_or_else(Q::one);
            let coefficient = if sign < 0 { -coefficient } else { coefficient };
            self.charge(1)?;
            constant += &factor.1.constant * &coefficient;
            for (id, value) in &factor.1.terms {
                terms.push((*id, value * &coefficient));
            }
            if self.eat_char('+')? {
                sign = 1;
            } else if self.eat_char('-')? {
                sign = -1;
            } else {
                break;
            }
        }
        let mut expression = Expr { constant, terms };
        expression.canonicalize()?;
        Ok(expression)
    }

    fn factor(&mut self, depth: usize) -> Result<Expr, String> {
        self.skip_ws();
        if self.peek().is_some_and(|byte| byte.is_ascii_digit()) {
            return Ok(Expr {
                constant: self.rational()?,
                terms: Vec::new(),
            });
        }
        if self.peek() == Some(b'x') {
            return Ok(Expr::var(self.coord()?));
        }
        if self.peek() == Some(b'(') {
            self.at += 1;
            let expression = self.expr_depth(depth + 1)?;
            self.expect_char(')')?;
            return Ok(expression);
        }
        Err("expected a rational, coordinate, or parenthesized expression".into())
    }

    fn optional_integer(&mut self) -> Result<Option<Ref>, String> {
        if self.eat_char(',')? {
            self.expect_ident("int")?;
            Ok(Some(self.reference()?))
        } else {
            Ok(None)
        }
    }

    fn expr_list(&mut self) -> Result<Vec<Expr>, String> {
        self.expect_char('(')?;
        let mut values = Vec::new();
        if self.eat_char(')')? {
            return Ok(values);
        }
        loop {
            let value = self.expr()?;
            self.charge(1)?;
            values.push(value);
            if self.eat_char(',')? {
                if self.eat_char(')')? {
                    break;
                }
            } else {
                self.expect_char(')')?;
                break;
            }
        }
        Ok(values)
    }

    fn ref_list(&mut self) -> Result<Vec<Ref>, String> {
        self.expect_char('(')?;
        let mut values = Vec::new();
        if self.eat_char(')')? {
            return Ok(values);
        }
        loop {
            let value = self.reference()?;
            self.charge(1)?;
            values.push(value);
            if self.eat_char(',')? {
                if self.eat_char(')')? {
                    break;
                }
            } else {
                self.expect_char(')')?;
                break;
            }
        }
        Ok(values)
    }

    fn coord_labels(&mut self) -> Result<Vec<(u32, u64)>, String> {
        self.expect_char('(')?;
        let mut values = Vec::new();
        if self.eat_char(')')? {
            return Ok(values);
        }
        loop {
            let id = self.coord()?;
            self.expect_char(':')?;
            let label = self.u64()?;
            self.charge(1)?;
            values.push((id, label));
            if self.eat_char(',')? {
                if self.eat_char(')')? {
                    break;
                }
            } else {
                self.expect_char(')')?;
                break;
            }
        }
        Ok(values)
    }

    fn q_pairs(&mut self) -> Result<Vec<(u32, Q)>, String> {
        self.expect_char('(')?;
        let mut values = Vec::new();
        if self.eat_char(')')? {
            return Ok(values);
        }
        loop {
            let id = self.u32()?;
            self.expect_char(':')?;
            let value = self.signed_q()?;
            self.charge(1)?;
            values.push((id, value));
            if self.eat_char(',')? {
                if self.eat_char(')')? {
                    break;
                }
            } else {
                self.expect_char(')')?;
                break;
            }
        }
        Ok(values)
    }

    fn field_u32(&mut self, name: &str) -> Result<u32, String> {
        self.expect_ident(name)?;
        self.expect_char('=')?;
        self.u32()
    }

    fn field_signed_q(&mut self, name: &str) -> Result<Q, String> {
        self.expect_ident(name)?;
        self.expect_char('=')?;
        self.signed_q()
    }

    fn field_expr(&mut self, name: &str) -> Result<Expr, String> {
        self.expect_ident(name)?;
        self.expect_char('=')?;
        self.expr()
    }

    fn field_exprs(&mut self, name: &str) -> Result<Vec<Expr>, String> {
        self.expect_ident(name)?;
        self.expect_char('=')?;
        self.expr_list()
    }

    fn field_refs(&mut self, name: &str) -> Result<Vec<Ref>, String> {
        self.expect_ident(name)?;
        self.expect_char('=')?;
        self.ref_list()
    }

    fn field_coord_labels(&mut self, name: &str) -> Result<Vec<(u32, u64)>, String> {
        self.expect_ident(name)?;
        self.expect_char('=')?;
        self.coord_labels()
    }

    fn field_q_pairs(&mut self, name: &str) -> Result<Vec<(u32, Q)>, String> {
        self.expect_ident(name)?;
        self.expect_char('=')?;
        self.q_pairs()
    }
}
