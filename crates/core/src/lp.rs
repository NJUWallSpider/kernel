//! Trusted exact importer for the explicitly documented linear LP v1 subset.
//! The parser never invokes a solver or converts a coefficient to floating point.
use crate::model::{
    check_q, parse_q, Expr, Model, Row, Var, MAX_LINE_BYTES, MAX_MPS_BYTES, MAX_NAME_BYTES,
    MAX_ROWS, MAX_TERMS, MAX_VARS, Q,
};
use num_traits::{One, Zero};
use std::collections::{HashMap, HashSet};

pub const MAX_LP_BYTES: usize = MAX_MPS_BYTES;
pub const MAX_LP_TOKENS: usize = 20_000_000;

fn invalid(s: &str) -> String {
    format!("INVALID LP: {s}")
}
fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT LP: {s}")
}
fn push<T>(v: &mut Vec<T>, x: T) -> Result<(), String> {
    v.try_reserve(1)
        .map_err(|_| resource("vector allocation"))?;
    v.push(x);
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Token<'a> {
    Name(&'a str),
    Number(&'a str),
    Plus,
    Minus,
    Colon,
    Le,
    Ge,
    Eq,
}
impl Token<'_> {
    fn relation(self) -> bool {
        matches!(self, Self::Le | Self::Ge | Self::Eq)
    }
}

fn reserved(s: &str) -> bool {
    matches!(
        s.to_ascii_lowercase().as_str(),
        "min"
            | "minimum"
            | "minimize"
            | "max"
            | "maximum"
            | "maximize"
            | "subject"
            | "to"
            | "such"
            | "that"
            | "st"
            | "s.t."
            | "st."
            | "bounds"
            | "bound"
            | "bin"
            | "binary"
            | "binaries"
            | "gen"
            | "general"
            | "generals"
            | "semi"
            | "semis"
            | "semi-continuous"
            | "end"
            | "free"
            | "inf"
            | "infinity"
            | "sos"
            | "lazy"
            | "scenario"
            | "scenarios"
            | "indicators"
            | "pwl"
            | "multi-objectives"
    )
}
fn name(s: &str) -> Result<(), String> {
    if s.len() > MAX_NAME_BYTES {
        return Err(resource("name length"));
    }
    if s.is_empty() || reserved(s) {
        return Err(invalid("empty or reserved name"));
    }
    if s.as_bytes()[0].eq_ignore_ascii_case(&b'e')
        && s.as_bytes()
            .get(1)
            .is_none_or(|c| c.is_ascii_digit() || c.eq_ignore_ascii_case(&b'e'))
    {
        return Err(invalid("exponent-ambiguous LP name"));
    }
    let mut chars = s.bytes();
    if !chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == b'_')
    {
        return Err(invalid(
            "name must start with an ASCII letter or underscore",
        ));
    }
    if !chars.all(|c| c.is_ascii_alphanumeric() || b"_.$#(),;!?@{}~%&".contains(&c)) {
        return Err(invalid("unsupported character in name"));
    }
    Ok(())
}

/// Signs are separate tokens, except inside numeric exponents or denominators.
/// A coefficient and its variable must be separated by whitespace.
fn tokenize(line: &str) -> Result<Vec<Token<'_>>, String> {
    let b = line.as_bytes();
    let mut i = 0;
    let mut out = Vec::new();
    while i < b.len() {
        if b[i].is_ascii_whitespace() {
            i += 1;
            continue;
        }
        let t = match b[i] {
            b'+' => {
                i += 1;
                Token::Plus
            }
            b'-' => {
                i += 1;
                Token::Minus
            }
            b':' => {
                i += 1;
                Token::Colon
            }
            b'=' => {
                i += 1;
                Token::Eq
            }
            b'<' | b'>' => {
                let sign = b[i];
                i += 1;
                if b.get(i) != Some(&b'=') {
                    return Err(invalid("strict inequalities and indicators unsupported"));
                }
                i += 1;
                if sign == b'<' {
                    Token::Le
                } else {
                    Token::Ge
                }
            }
            c if c.is_ascii_digit() || c == b'.' => {
                let start = i;
                while b.get(i).is_some_and(|c| c.is_ascii_digit() || *c == b'.') {
                    i += 1;
                }
                if b.get(i).is_some_and(|c| b"eEdD".contains(c)) {
                    i += 1;
                    if b.get(i).is_some_and(|c| *c == b'+' || *c == b'-') {
                        i += 1;
                    }
                    while b.get(i).is_some_and(u8::is_ascii_digit) {
                        i += 1;
                    }
                }
                if b.get(i) == Some(&b'/') {
                    i += 1;
                    if b.get(i).is_some_and(|c| *c == b'+' || *c == b'-') {
                        i += 1;
                    }
                    while b.get(i).is_some_and(u8::is_ascii_digit) {
                        i += 1;
                    }
                }
                if b.get(i)
                    .is_some_and(|c| !c.is_ascii_whitespace() && !b"+-:<=>".contains(c))
                {
                    return Err(invalid("numeric token must be separated from a variable"));
                }
                Token::Number(&line[start..i])
            }
            c if c.is_ascii_alphabetic() || c == b'_' => {
                let start = i;
                while b
                    .get(i)
                    .is_some_and(|c| c.is_ascii_alphanumeric() || b"_.$#(),;!?@{}~%&".contains(c))
                {
                    i += 1;
                }
                let text = &line[start..i];
                if text.len() > MAX_NAME_BYTES {
                    return Err(resource("name length"));
                }
                Token::Name(text)
            }
            _ => {
                return Err(invalid(
                    "unsupported token (including nonlinear or quoted syntax)",
                ))
            }
        };
        push(&mut out, t)?;
    }
    Ok(out)
}

#[derive(Default)]
struct Bounds {
    lower: Option<Option<Q>>,
    upper: Option<Option<Q>>,
    binary: bool,
    typed: bool,
}
struct Builder {
    model: Model,
    names: HashMap<String, usize>,
    row_names: HashSet<String>,
    bounds: Vec<Bounds>,
    entries: usize,
}
impl Builder {
    fn new() -> Self {
        Self {
            model: Model {
                name: "LP".into(),
                vars: Vec::new(),
                rows: Vec::new(),
                objective: Expr::zero(),
            },
            names: HashMap::new(),
            row_names: HashSet::new(),
            bounds: Vec::new(),
            entries: 0,
        }
    }
    fn var(&mut self, s: &str) -> Result<u32, String> {
        name(s)?;
        if let Some(&id) = self.names.get(s) {
            return Ok(id as u32);
        }
        if self.model.vars.len() >= MAX_VARS {
            return Err(resource("variable dimension"));
        }
        let id = self.model.vars.len();
        self.names
            .try_reserve(1)
            .map_err(|_| resource("variable index allocation"))?;
        self.names.insert(s.to_owned(), id);
        push(
            &mut self.model.vars,
            Var {
                name: s.to_owned(),
                integer: false,
                lower: Some(Q::zero()),
                upper: None,
            },
        )?;
        push(&mut self.bounds, Bounds::default())?;
        Ok(id as u32)
    }
    fn expr(&mut self, tokens: &[Token<'_>]) -> Result<Expr, String> {
        if tokens.is_empty() {
            return Err(invalid("empty affine expression"));
        }
        let mut e = Expr::zero();
        let mut i = 0;
        let mut first = true;
        while i < tokens.len() {
            let negative = match tokens[i] {
                Token::Plus => {
                    i += 1;
                    false
                }
                Token::Minus => {
                    i += 1;
                    true
                }
                _ if first => false,
                _ => return Err(invalid("missing plus/minus between affine terms")),
            };
            let mut q = Q::one();
            let numeric = if let Some(Token::Number(s)) = tokens.get(i) {
                q = parse_q(s)?;
                i += 1;
                true
            } else {
                false
            };
            if negative {
                q = -q;
            }
            if let Some(Token::Name(s)) = tokens.get(i) {
                let id = self.var(s)?;
                i += 1;
                self.entries = self
                    .entries
                    .checked_add(1)
                    .ok_or_else(|| resource("coefficient count"))?;
                if self.entries > MAX_TERMS {
                    return Err(resource("coefficient entries"));
                }
                // Register the variable even when its coefficient is zero.
                if !q.is_zero() {
                    push(&mut e.terms, (id, q))?;
                }
            } else if numeric {
                e.constant += q;
                check_q(&e.constant)?;
            } else {
                return Err(invalid("missing affine term after sign"));
            }
            first = false;
        }
        e.canonicalize()?;
        Ok(e)
    }
    fn objective(&mut self, tokens: &[Token<'_>], maximize: bool) -> Result<(), String> {
        let tokens = if let [Token::Name(s), Token::Colon, rest @ ..] = tokens {
            name(s)?;
            rest
        } else {
            tokens
        };
        let e = self.expr(tokens)?;
        self.model.objective = if maximize { e.scaled(&-Q::one())? } else { e };
        Ok(())
    }
    fn row(&mut self, tokens: &[Token<'_>]) -> Result<(), String> {
        if self.model.rows.len() >= MAX_ROWS {
            return Err(resource("row dimension"));
        }
        let (row_name, tokens) = if let [Token::Name(s), Token::Colon, rest @ ..] = tokens {
            name(s)?;
            (s.to_string(), rest)
        } else {
            (format!("_lp_row_{}", self.model.rows.len()), tokens)
        };
        self.row_names
            .try_reserve(1)
            .map_err(|_| resource("row index allocation"))?;
        if !self.row_names.insert(row_name.clone()) {
            return Err(invalid("duplicate constraint name"));
        }
        let relations: Vec<usize> = tokens
            .iter()
            .enumerate()
            .filter(|(_, t)| t.relation())
            .map(|(i, _)| i)
            .collect();
        let (mut e, mut lower, mut upper) = match relations.as_slice() {
            [a] => {
                let mut e = self.expr(&tokens[..*a])?;
                let right = self.expr(&tokens[*a + 1..])?;
                e.add_scaled(&right, &-Q::one())?;
                let zero = Some(Q::zero());
                match tokens[*a] {
                    Token::Le => (e, None, zero),
                    Token::Ge => (e, zero, None),
                    Token::Eq => (e, zero.clone(), zero),
                    _ => unreachable!(),
                }
            }
            [a, b] => {
                if tokens[*a] != tokens[*b] || tokens[*a] == Token::Eq {
                    return Err(invalid("range requires two matching <= or >= relations"));
                }
                let left = self.expr(&tokens[..*a])?;
                let middle = self.expr(&tokens[*a + 1..*b])?;
                let right = self.expr(&tokens[*b + 1..])?;
                if !left.terms.is_empty() || !right.terms.is_empty() {
                    return Err(invalid("range endpoints must be constant"));
                }
                if tokens[*a] == Token::Le {
                    (middle, Some(left.constant), Some(right.constant))
                } else {
                    (middle, Some(right.constant), Some(left.constant))
                }
            }
            _ => {
                return Err(invalid(
                    "constraint needs one relation or one ranged relation",
                ))
            }
        };
        // Normalize every row constant into its bounds, as MPS already does.
        for bound in [&mut lower, &mut upper].into_iter().flatten() {
            *bound -= &e.constant;
            check_q(bound)?;
        }
        e.constant = Q::zero();
        push(
            &mut self.model.rows,
            Row {
                name: row_name,
                expr: e,
                lower,
                upper,
            },
        )
    }
    fn bound(&mut self, tokens: &[Token<'_>]) -> Result<(), String> {
        if let [Token::Name(v), Token::Name(free)] = tokens {
            if !free.eq_ignore_ascii_case("free") {
                return Err(invalid("invalid free bound"));
            }
            let id = self.var(v)? as usize;
            set_bound(&mut self.bounds[id].lower, None)?;
            return set_bound(&mut self.bounds[id].upper, None);
        }
        let relations: Vec<usize> = tokens
            .iter()
            .enumerate()
            .filter(|(_, t)| t.relation())
            .map(|(i, _)| i)
            .collect();
        let (id, lower, upper) = match relations.as_slice() {
            [a] => {
                if let Some(v) = bound_variable(&tokens[..*a]) {
                    let id = self.var(v)? as usize;
                    let n = bound_value(&tokens[*a + 1..])?;
                    match tokens[*a] {
                        Token::Le => (id, None, Some(n.for_upper()?)),
                        Token::Ge => (id, Some(n.for_lower()?), None),
                        Token::Eq => {
                            let n = n.finite()?;
                            (id, Some(Some(n.clone())), Some(Some(n)))
                        }
                        _ => unreachable!(),
                    }
                } else if let Some(v) = bound_variable(&tokens[*a + 1..]) {
                    let n = bound_value(&tokens[..*a])?;
                    let id = self.var(v)? as usize;
                    match tokens[*a] {
                        Token::Le => (id, Some(n.for_lower()?), None),
                        Token::Ge => (id, None, Some(n.for_upper()?)),
                        Token::Eq => {
                            let n = n.finite()?;
                            (id, Some(Some(n.clone())), Some(Some(n)))
                        }
                        _ => unreachable!(),
                    }
                } else {
                    return Err(invalid(
                        "bound must constrain exactly one unscaled variable",
                    ));
                }
            }
            [a, b] => {
                if tokens[*a] != tokens[*b] || tokens[*a] == Token::Eq {
                    return Err(invalid("invalid ranged bound directions"));
                }
                let [Token::Name(v)] = &tokens[*a + 1..*b] else {
                    return Err(invalid("ranged bound must constrain one variable"));
                };
                let left = bound_value(&tokens[..*a])?;
                let right = bound_value(&tokens[*b + 1..])?;
                let id = self.var(v)? as usize;
                if tokens[*a] == Token::Le {
                    (id, Some(left.for_lower()?), Some(right.for_upper()?))
                } else {
                    (id, Some(right.for_lower()?), Some(left.for_upper()?))
                }
            }
            _ => return Err(invalid("invalid bound record")),
        };
        if let Some(lower) = lower {
            set_bound(&mut self.bounds[id].lower, lower)?;
        }
        if let Some(upper) = upper {
            set_bound(&mut self.bounds[id].upper, upper)?;
        }
        Ok(())
    }
    fn types(&mut self, tokens: &[Token<'_>], binary: bool) -> Result<(), String> {
        for t in tokens {
            let Token::Name(v) = t else {
                return Err(invalid("type list must contain only variable names"));
            };
            let id = self.var(v)? as usize;
            if self.bounds[id].typed {
                return Err(invalid("repeated or conflicting variable type declaration"));
            }
            self.bounds[id].typed = true;
            self.bounds[id].binary = binary;
            self.model.vars[id].integer = true;
        }
        Ok(())
    }
    fn finish(mut self) -> Result<Model, String> {
        for (v, b) in self.model.vars.iter_mut().zip(self.bounds) {
            if let Some(lower) = b.lower {
                v.lower = lower;
            }
            if let Some(upper) = b.upper {
                v.upper = upper;
            }
            if b.binary {
                if v.lower.as_ref().is_none_or(|q| q < &Q::zero()) {
                    v.lower = Some(Q::zero());
                }
                if v.upper.as_ref().is_none_or(|q| q > &Q::one()) {
                    v.upper = Some(Q::one());
                }
            }
        }
        self.model.validate()?;
        Ok(self.model)
    }
}
fn set_bound(slot: &mut Option<Option<Q>>, value: Option<Q>) -> Result<(), String> {
    if slot.as_ref().is_some_and(|old| old != &value) {
        return Err(invalid("conflicting repeated bound definition"));
    }
    *slot = Some(value);
    Ok(())
}
enum BoundValue {
    Finite(Q),
    NegInf,
    PosInf,
}
fn bound_variable<'a>(tokens: &[Token<'a>]) -> Option<&'a str> {
    match tokens {
        [Token::Name(s)] if !reserved(s) => Some(s),
        _ => None,
    }
}
impl BoundValue {
    fn for_lower(self) -> Result<Option<Q>, String> {
        match self {
            Self::Finite(q) => Ok(Some(q)),
            Self::NegInf => Ok(None),
            Self::PosInf => Err(invalid("positive infinite lower bound unsupported")),
        }
    }
    fn for_upper(self) -> Result<Option<Q>, String> {
        match self {
            Self::Finite(q) => Ok(Some(q)),
            Self::PosInf => Ok(None),
            Self::NegInf => Err(invalid("negative infinite upper bound unsupported")),
        }
    }
    fn finite(self) -> Result<Q, String> {
        match self {
            Self::Finite(q) => Ok(q),
            _ => Err(invalid("infinite equality bound")),
        }
    }
}
fn bound_value(tokens: &[Token<'_>]) -> Result<BoundValue, String> {
    let (negative, tokens) = match tokens.first() {
        Some(Token::Minus) => (true, &tokens[1..]),
        Some(Token::Plus) => (false, &tokens[1..]),
        _ => (false, tokens),
    };
    match tokens {
        [Token::Number(s)] => {
            let q = parse_q(s)?;
            Ok(BoundValue::Finite(if negative { -q } else { q }))
        }
        [Token::Name(s)] if s.eq_ignore_ascii_case("inf") || s.eq_ignore_ascii_case("infinity") => {
            Ok(if negative {
                BoundValue::NegInf
            } else {
                BoundValue::PosInf
            })
        }
        _ => Err(invalid("bound value must be one signed scalar or infinity")),
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Section {
    Start,
    Objective,
    Rows,
    Bounds,
    Binary,
    General,
    Semi,
    End,
}
fn header(line: &str) -> Option<(Section, bool)> {
    let s = line
        .split_ascii_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_ascii_lowercase();
    match s.as_str() {
        "min" | "minimum" | "minimize" => Some((Section::Objective, false)),
        "max" | "maximum" | "maximize" => Some((Section::Objective, true)),
        "st" | "st." | "s.t." | "subject to" | "such that" => Some((Section::Rows, false)),
        "bounds" | "bound" => Some((Section::Bounds, false)),
        "binary" | "binaries" | "bin" => Some((Section::Binary, false)),
        "general" | "generals" | "gen" => Some((Section::General, false)),
        "semi" | "semis" | "semi-continuous" => Some((Section::Semi, false)),
        "end" => Some((Section::End, false)),
        _ => None,
    }
}

/// Named constraints can span lines. Unnamed constraints occupy one physical
/// line each; mixing named/unnamed rows is rejected to avoid line ambiguities.
pub fn parse_lp(input: &str) -> Result<Model, String> {
    if input.len() > MAX_LP_BYTES {
        return Err(resource("input byte budget"));
    }
    if !input.is_ascii() {
        return Err(invalid("input must be ASCII"));
    }
    let mut builder = Builder::new();
    let mut section = Section::Start;
    let mut maximize = false;
    let mut objective = Vec::new();
    let mut pending_row = Vec::new();
    let mut named_rows = None;
    let mut total_tokens = 0usize;
    let mut seen = [false; 4];
    for (line_number, line) in input.lines().enumerate() {
        let context = |e: String| format!("{e} (line {})", line_number + 1);
        if line.len() > MAX_LINE_BYTES {
            return Err(resource("line byte budget"));
        }
        if line.bytes().any(|c| c.is_ascii_control() && c != b'\t') {
            return Err(invalid("control character"));
        }
        let line = line.split('\\').next().unwrap().trim();
        if line.is_empty() {
            continue;
        }
        if section == Section::End {
            return Err(invalid("content after End"));
        }
        if let Some((next, sense)) = header(line) {
            let valid = match next {
                Section::Objective => section == Section::Start,
                Section::Rows => section == Section::Objective,
                Section::Bounds => section == Section::Rows && !seen[0],
                Section::Binary | Section::General | Section::Semi => matches!(
                    section,
                    Section::Rows
                        | Section::Bounds
                        | Section::Binary
                        | Section::General
                        | Section::Semi
                ),
                Section::End => matches!(
                    section,
                    Section::Rows
                        | Section::Bounds
                        | Section::Binary
                        | Section::General
                        | Section::Semi
                ),
                _ => false,
            };
            if !valid {
                return Err(context(invalid("misplaced or repeated section")));
            }
            if section == Section::Objective {
                builder.objective(&objective, maximize).map_err(&context)?;
                objective.clear();
            }
            if section == Section::Rows && !pending_row.is_empty() {
                builder.row(&pending_row).map_err(&context)?;
                pending_row.clear();
            }
            let index = match next {
                Section::Bounds => Some(0),
                Section::Binary => Some(1),
                Section::General => Some(2),
                Section::Semi => Some(3),
                _ => None,
            };
            if let Some(i) = index {
                if seen[i] {
                    return Err(context(invalid("repeated section")));
                }
                seen[i] = true;
            }
            if next == Section::Objective {
                maximize = sense;
            }
            section = next;
            continue;
        }
        let tokens = tokenize(line).map_err(&context)?;
        total_tokens = total_tokens
            .checked_add(tokens.len())
            .ok_or_else(|| resource("token count overflow"))?;
        if total_tokens > MAX_LP_TOKENS {
            return Err(resource("token budget"));
        }
        match section {
            Section::Objective => {
                objective
                    .try_reserve(tokens.len())
                    .map_err(|_| resource("objective token allocation"))?;
                objective.extend(tokens);
            }
            Section::Rows => {
                let labelled = matches!(tokens.as_slice(), [Token::Name(_), Token::Colon, ..]);
                let mode = *named_rows.get_or_insert(labelled);
                if mode {
                    if labelled && !pending_row.is_empty() {
                        builder.row(&pending_row).map_err(&context)?;
                        pending_row.clear();
                    }
                    pending_row
                        .try_reserve(tokens.len())
                        .map_err(|_| resource("row token allocation"))?;
                    pending_row.extend(tokens);
                } else {
                    if labelled {
                        return Err(context(invalid("mixed named and unnamed constraints")));
                    }
                    builder.row(&tokens).map_err(&context)?;
                }
            }
            Section::Bounds => builder.bound(&tokens).map_err(&context)?,
            Section::Binary | Section::General => builder
                .types(&tokens, section == Section::Binary)
                .map_err(&context)?,
            Section::Semi => {
                return Err(context(invalid(
                    "nonempty semicontinuous section unsupported",
                )))
            }
            _ => return Err(context(invalid("expected a standalone LP section header"))),
        }
    }
    if section != Section::End {
        return Err(invalid("missing End"));
    }
    builder.finish()
}
