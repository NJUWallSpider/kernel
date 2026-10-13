//! Trusted exact MILP model and deliberately bounded MPS reader.
//!
//! The objective is always minimized. A maximization objective, including its
//! constant, is negated. Names and input order are retained for model binding.
//! No floating point value participates in this module.

use num_bigint::BigInt;
use num_integer::Integer;
use num_rational::BigRational;
use num_traits::{One, Signed, Zero};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

pub type Q = BigRational;
pub const MAX_DECIMAL_DIGITS: usize = 4096;
pub const MAX_Q_BITS: u64 = 65_536;
pub const MAX_VARS: usize = 2_000_000;
pub const MAX_ROWS: usize = 2_000_000;
pub const MAX_TERMS: usize = 20_000_000;
pub const MAX_MPS_BYTES: usize = 512 * 1024 * 1024;
pub const MAX_LINE_BYTES: usize = 32_768;
pub const MAX_NAME_BYTES: usize = 1024;

fn resource(what: &str) -> String {
    format!("RESOURCE_LIMIT: {what}")
}

fn push<T>(out: &mut Vec<T>, value: T) -> Result<(), String> {
    out.try_reserve(1)
        .map_err(|_| resource("model vector allocation"))?;
    out.push(value);
    Ok(())
}

/// Also checks canonical representation, since `Ratio::new_raw` and external
/// decoders can construct a noncanonical or zero-denominator rational.
pub fn check_q(q: &Q) -> Result<(), String> {
    if q.numer().bits() > MAX_Q_BITS || q.denom().bits() > MAX_Q_BITS {
        return Err(resource("rational bit budget"));
    }
    // Every integer, including zero and negative integers, has a canonical
    // denominator of one. The bit checks above still precede this shortcut.
    if q.denom().is_one() {
        return Ok(());
    }
    if q.denom() <= &BigInt::zero() || q.numer().gcd(q.denom()) != BigInt::one() {
        return Err("noncanonical rational or nonpositive denominator".into());
    }
    Ok(())
}

/// Exact decimal/scientific notation (`e`, `E`, `d`, `D`) or integer fraction.
/// Fraction components are signed integers; denominator zero is rejected.
pub fn parse_q(text: &str) -> Result<Q, String> {
    if text.len() > 2 * MAX_DECIMAL_DIGITS + 32 {
        return Err(resource("number text budget"));
    }
    if text.is_empty() || !text.is_ascii() || text.bytes().any(|c| c.is_ascii_whitespace()) {
        return Err(format!("invalid rational {text:?}"));
    }
    fn integer(s: &str) -> Result<BigInt, String> {
        let digits = s.strip_prefix(['+', '-']).unwrap_or(s);
        if digits.len() > MAX_DECIMAL_DIGITS {
            return Err(resource("integer digit budget"));
        }
        if digits.is_empty() || !digits.bytes().all(|c| c.is_ascii_digit()) {
            return Err("invalid integer literal".into());
        }
        s.parse::<BigInt>()
            .map_err(|_| "invalid integer literal".into())
    }
    if let Some((n, d)) = text.split_once('/') {
        let (n, d) = (integer(n)?, integer(d)?);
        if d.is_zero() {
            return Err("zero denominator".into());
        }
        let q = Q::new(n, d);
        check_q(&q)?;
        return Ok(q);
    }
    let split = text.find(['e', 'E', 'd', 'D']);
    let (mantissa, exp) = if let Some(i) = split {
        let e = &text[i + 1..];
        let digits = e.strip_prefix(['+', '-']).unwrap_or(e);
        if digits.is_empty() || !digits.bytes().all(|c| c.is_ascii_digit()) {
            return Err("invalid decimal exponent".into());
        }
        // An arbitrarily long exponent is rejected before machine conversion.
        if digits.len() > 6 {
            return Err(resource("decimal exponent budget"));
        }
        let e = e
            .parse::<i64>()
            .map_err(|_| resource("decimal exponent budget"))?;
        if e.unsigned_abs() > MAX_DECIMAL_DIGITS as u64 {
            return Err(resource("decimal exponent budget"));
        }
        (&text[..i], e)
    } else {
        (text, 0)
    };
    let negative = mantissa.starts_with('-');
    let unsigned = mantissa.strip_prefix(['+', '-']).unwrap_or(mantissa);
    let mut digits = String::new();
    let mut decimal = None;
    for ch in unsigned.bytes() {
        if ch == b'.' && decimal.is_none() {
            decimal = Some(digits.len());
        } else if ch.is_ascii_digit() {
            digits.push(ch as char);
        } else {
            return Err("invalid decimal mantissa".into());
        }
    }
    if digits.is_empty() {
        return Err("empty decimal mantissa".into());
    }
    if digits.len() > MAX_DECIMAL_DIGITS {
        return Err(resource("decimal digit budget"));
    }
    let fractional = decimal.map_or(0, |i| digits.len() - i) as i64;
    let power = exp - fractional;
    if power.unsigned_abs() > MAX_DECIMAL_DIGITS as u64 {
        return Err(resource("effective decimal exponent budget"));
    }
    let mut n = integer(&digits)?;
    if negative {
        n = -n;
    }
    let ten = BigInt::from(10u32).pow(power.unsigned_abs() as u32);
    let q = if power < 0 {
        Q::new(n, ten)
    } else {
        Q::from_integer(n * ten)
    };
    check_q(&q)?;
    Ok(q)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Expr {
    #[serde(with = "crate::rpa::scalar")]
    pub constant: Q,
    #[serde(with = "crate::rpa::expr_terms")]
    pub terms: Vec<(u32, Q)>,
}

impl Expr {
    pub fn zero() -> Self {
        Self {
            constant: Q::zero(),
            terms: Vec::new(),
        }
    }
    pub fn var(id: u32) -> Self {
        Self {
            constant: Q::zero(),
            terms: vec![(id, Q::one())],
        }
    }
    pub fn validate(&self, nvars: usize) -> Result<(), String> {
        check_q(&self.constant)?;
        if self.terms.len() > MAX_TERMS {
            return Err(resource("expression term budget"));
        }
        let mut previous = None;
        for (id, q) in &self.terms {
            check_q(q)?;
            if *id as usize >= nvars || previous.is_some_and(|p| p >= *id) || q.is_zero() {
                return Err("expression has invalid, duplicate, unsorted, or zero term".into());
            }
            previous = Some(*id);
        }
        Ok(())
    }
    pub fn canonicalize(&mut self) -> Result<(), String> {
        check_q(&self.constant)?;
        if self.terms.len() > MAX_TERMS {
            return Err(resource("expression term budget"));
        }
        for (_, q) in &self.terms {
            check_q(q)?;
        }
        self.terms.sort_unstable_by_key(|(id, _)| *id);
        let mut result: Vec<(u32, Q)> = Vec::new();
        for (id, q) in std::mem::take(&mut self.terms) {
            if q.is_zero() {
                continue;
            }
            if let Some((prev, value)) = result.last_mut() {
                if *prev == id {
                    *value += q;
                    check_q(value)?;
                    if value.is_zero() {
                        result.pop();
                    }
                    continue;
                }
            }
            push(&mut result, (id, q))?;
        }
        self.terms = result;
        Ok(())
    }
    pub fn scaled(&self, scale: &Q) -> Result<Self, String> {
        check_q(scale)?;
        self.validate(MAX_VARS)?;
        if scale.is_zero() {
            return Ok(Self::zero());
        }
        let one = scale.is_one();
        let minus_one = scale.denom().is_one()
            && scale.numer().is_negative() && scale.numer().magnitude().is_one();
        let product = |q: &Q| {
            if one { q.clone() } else if minus_one { -q } else { q * scale }
        };
        let mut out = Self {
            constant: product(&self.constant),
            terms: Vec::new(),
        };
        check_q(&out.constant)?;
        out.terms
            .try_reserve(self.terms.len())
            .map_err(|_| resource("expression allocation"))?;
        for (id, q) in &self.terms {
            let q = product(q);
            check_q(&q)?;
            out.terms.push((*id, q));
        }
        Ok(out)
    }
    pub fn add_scaled(&mut self, other: &Self, scale: &Q) -> Result<(), String> {
        check_q(scale)?;
        self.validate(MAX_VARS)?;
        other.validate(MAX_VARS)?;
        if scale.is_zero() {
            return Ok(());
        }
        if self
            .terms
            .len()
            .checked_add(other.terms.len())
            .is_none_or(|n| n > MAX_TERMS)
        {
            return Err(resource("expression addition term budget"));
        }
        let constant_product = &other.constant * scale;
        check_q(&constant_product)?;
        self.constant += constant_product;
        check_q(&self.constant)?;
        self.terms
            .try_reserve(other.terms.len())
            .map_err(|_| resource("expression allocation"))?;
        for (id, q) in &other.terms {
            let q = q * scale;
            check_q(&q)?;
            self.terms.push((*id, q));
        }
        self.canonicalize()
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Var {
    pub name: String,
    pub integer: bool,
    pub lower: Option<Q>,
    pub upper: Option<Q>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Row {
    pub name: String,
    pub expr: Expr,
    pub lower: Option<Q>,
    pub upper: Option<Q>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Model {
    pub name: String,
    pub vars: Vec<Var>,
    pub rows: Vec<Row>,
    pub objective: Expr,
}

fn check_name(name: &str) -> Result<(), String> {
    if name.len() > MAX_NAME_BYTES {
        return Err(resource("name budget"));
    }
    if name.is_empty() || !name.is_ascii() || name.bytes().any(|c| c.is_ascii_control()) {
        return Err("empty, non-ASCII, or control-character name".into());
    }
    Ok(())
}
impl Model {
    pub fn validate(&self) -> Result<(), String> {
        check_name(&self.name)?;
        if self.vars.len() > MAX_VARS || self.rows.len() > MAX_ROWS {
            return Err(resource("model dimension budget"));
        }
        let mut names = HashSet::new();
        names
            .try_reserve(self.vars.len().max(self.rows.len()))
            .map_err(|_| resource("model name-set allocation"))?;
        for v in &self.vars {
            check_name(&v.name)?;
            if !names.insert(&v.name) {
                return Err("duplicate variable name".into());
            }
            for q in [&v.lower, &v.upper].into_iter().flatten() {
                check_q(q)?;
            }
        }
        names.clear();
        let mut count = self.objective.terms.len();
        self.objective.validate(self.vars.len())?;
        for row in &self.rows {
            check_name(&row.name)?;
            if !names.insert(&row.name) {
                return Err("duplicate row name".into());
            }
            row.expr.validate(self.vars.len())?;
            for q in [&row.lower, &row.upper].into_iter().flatten() {
                check_q(q)?;
            }
            count = count
                .checked_add(row.expr.terms.len())
                .ok_or_else(|| resource("term count overflow"))?;
            if count > MAX_TERMS {
                return Err(resource("model term budget"));
            }
        }
        // Contradictory bounds describe the empty feasible set and remain valid.
        Ok(())
    }
}

/// Canonical JSON export of a model: exactly `name`, `variables`, `rows` and
/// `objective`, in that order. Vector order is the model's own canonical order,
/// so no emitted key depends on hash iteration.
///
/// Scalars reuse the RPA textual vocabulary (`crate::rpa::scalar`, i.e. the
/// `rat::Display` / `parse_q` round trip): integers as `"-3"`, fractions as
/// `"-3/2"`, unbounded sides as JSON `null`. The exported value is exactly the
/// model, so nothing here consults `Model::validate`; a model that has not been
/// validated (or one validation would reject) still exports faithfully.
pub fn to_json(model: &Model) -> serde_json::Value {
    #[derive(Serialize)]
    struct JsonVar<'a> {
        name: &'a str,
        integer: bool,
        #[serde(with = "crate::rpa::option_scalar")]
        lower: &'a Option<Q>,
        #[serde(with = "crate::rpa::option_scalar")]
        upper: &'a Option<Q>,
    }
    #[derive(Serialize)]
    struct JsonRow<'a> {
        name: &'a str,
        expr: &'a Expr,
        #[serde(with = "crate::rpa::option_scalar")]
        lower: &'a Option<Q>,
        #[serde(with = "crate::rpa::option_scalar")]
        upper: &'a Option<Q>,
    }
    #[derive(Serialize)]
    struct JsonModel<'a> {
        name: &'a str,
        variables: Vec<JsonVar<'a>>,
        rows: Vec<JsonRow<'a>>,
        objective: &'a Expr,
    }
    let value = JsonModel {
        name: &model.name,
        variables: model
            .vars
            .iter()
            .map(|v| JsonVar {
                name: &v.name,
                integer: v.integer,
                lower: &v.lower,
                upper: &v.upper,
            })
            .collect(),
        rows: model
            .rows
            .iter()
            .map(|r| JsonRow {
                name: &r.name,
                expr: &r.expr,
                lower: &r.lower,
                upper: &r.upper,
            })
            .collect(),
        objective: &model.objective,
    };
    // Cannot fail: the shape above is a plain data tree with string/boolean/
    // integer leaves, so no map key and no number is out of range.
    serde_json::to_value(&value).expect("canonical model JSON is representable")
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Section {
    Start,
    Name,
    Sense,
    ObjName,
    Rows,
    Columns,
    Rhs,
    Ranges,
    Bounds,
    End,
}

struct RawRow {
    kind: char,
    name: String,
    expr: Expr,
    rhs: Option<Q>,
    range: Option<Q>,
}
#[derive(Default)]
struct BoundState {
    seen: bool,
    lower: Option<Option<Q>>,
    upper: Option<Option<Q>>,
    binary: bool,
}

fn set_bound(slot: &mut Option<Option<Q>>, value: Option<Q>) -> Result<(), String> {
    if slot.as_ref().is_some_and(|old| old != &value) {
        return Err("conflicting repeated bound definition (unsupported MPS dialect)".into());
    }
    *slot = Some(value);
    Ok(())
}

// Fixed-format embedded blanks are meaningful in some readers. This subset
// does not permit them: never reinterpret such a card as extra free tokens.
fn reject_embedded_fixed_names(
    line: &str,
    section: Section,
    variables: &HashMap<String, usize>,
) -> Result<(), String> {
    let minimum = match section {
        Section::Rows => 5,
        Section::Bounds => 15,
        Section::Columns | Section::Rhs | Section::Ranges => 25,
        _ => return Ok(()),
    };
    if line.len() < minimum {
        return Ok(());
    }
    let field = |start: usize, end: usize| -> &str {
        if start >= line.len() {
            ""
        } else {
            &line[start..end.min(line.len())]
        }
    };
    if section == Section::Bounds {
        // A genuine fixed bound card references its variable at columns 15-22.
        // Free cards such as " LO bnd  obj  1104" happen to align some gaps,
        // but do not have a fixed-column variable/value at all.
        if !variables.contains_key(field(14, 22).trim()) {
            return Ok(());
        }
        if matches!(field(1, 3), "LO" | "LI" | "UP" | "UI" | "FX")
            && field(24, 36).trim().is_empty()
        {
            return Ok(());
        }
    }
    let blank = |start, end| field(start, end).bytes().all(|c| c == b' ');
    let (gaps, names): (&[(usize, usize)], &[(usize, usize)]) = match section {
        Section::Rows => (&[(0, 1), (3, 4), (12, usize::MAX)], &[(4, 12)]),
        Section::Columns | Section::Rhs | Section::Ranges => (
            &[
                (0, 4),
                (12, 14),
                (22, 24),
                (36, 39),
                (47, 49),
                (61, usize::MAX),
            ],
            &[(4, 12), (14, 22), (39, 47)],
        ),
        Section::Bounds => (
            &[(0, 1), (3, 4), (12, 14), (22, 24), (36, usize::MAX)],
            &[(4, 12), (14, 22)],
        ),
        _ => return Ok(()),
    };
    if gaps.iter().all(|&(a, b)| blank(a, b))
        && names
            .iter()
            .any(|&(a, b)| field(a, b).trim().bytes().any(|c| c.is_ascii_whitespace()))
    {
        return Err("embedded-space fixed-format names unsupported".into());
    }
    Ok(())
}

/// Strict linear MPS subset: one objective N row, one RHS/range/bound vector,
/// finite exact numbers, LO/UP/FX/FR/MI/PL/BV/LI/UI, integer markers and ranges.
/// Fixed-column continuation cards and whitespace-free fixed names are accepted.
/// Embedded-space names, multiple objectives/vectors, nonlinear extensions and
/// order-dependent repeated bounds are rejected rather than guessed.
pub fn parse_mps(input: &str) -> Result<Model, String> {
    if input.len() > MAX_MPS_BYTES {
        return Err(resource("MPS byte budget"));
    }
    if !input.is_ascii() {
        return Err("MPS must be ASCII".into());
    }
    let mut section = Section::Start;
    let mut name = "MODEL".to_string();
    let mut maximize = false;
    let mut sense_seen = false;
    let mut sense_value = false;
    let mut objname_seen = false;
    let mut objname: Option<String> = None;
    let mut rows: Vec<RawRow> = Vec::new();
    let mut row_ids: HashMap<String, usize> = HashMap::new();
    let mut vars: Vec<Var> = Vec::new();
    let mut var_ids: HashMap<String, usize> = HashMap::new();
    let mut bounds: Vec<BoundState> = Vec::new();
    let mut in_integer = false;
    let mut last_column: Option<String> = None;
    let mut rhs_name: Option<String> = None;
    let mut range_name: Option<String> = None;
    let mut bound_name: Option<String> = None;
    let mut entries = 0usize;
    let mut seen_rhs = false;
    let mut seen_ranges = false;
    let mut seen_bounds = false;
    for (line_index, line) in input.lines().enumerate() {
        let fail = |s: &str| {
            if s.starts_with("RESOURCE_LIMIT") {
                format!("{s} (MPS line {})", line_index + 1)
            } else {
                format!("MPS line {}: {s}", line_index + 1)
            }
        };
        if line.len() > MAX_LINE_BYTES {
            return Err(resource("MPS line budget"));
        }
        if line.starts_with('*') || line.trim().is_empty() {
            continue;
        }
        if section == Section::End {
            return Err(fail("data after ENDATA"));
        }
        if line.bytes().any(|c| c.is_ascii_control() && c != b'\t') {
            return Err(fail("control byte"));
        }
        let mut t: Vec<&str> = line.split_ascii_whitespace().collect();
        // A '$' comment beginning a separate token is supported; an attached '$'
        // remains part of the name, so it cannot silently truncate model data.
        if let Some(i) = t.iter().position(|s| s.starts_with('$')) {
            t.truncate(i);
        }
        if t.is_empty() {
            continue;
        }
        if !line.starts_with([' ', '\t']) {
            if in_integer {
                return Err(fail("unclosed integer marker"));
            }
            match t[0] {
                "NAME" if section == Section::Start && t.len() <= 2 => {
                    if t.len() == 2 {
                        name = t[1].to_owned();
                        check_name(&name)?;
                    }
                    section = Section::Name;
                }
                "OBJSENSE"
                    if matches!(section, Section::Name | Section::ObjName)
                        && !sense_seen
                        && t.len() <= 2 =>
                {
                    if objname_seen && objname.is_none() {
                        return Err(fail("missing OBJNAME value"));
                    }
                    sense_seen = true;
                    section = Section::Sense;
                    if t.len() == 2 {
                        maximize = parse_sense(t[1])?;
                        sense_value = true;
                    }
                }
                "OBJNAME"
                    if matches!(section, Section::Name | Section::Sense)
                        && !objname_seen
                        && t.len() <= 2 =>
                {
                    if sense_seen && !sense_value {
                        return Err(fail("missing OBJSENSE value"));
                    }
                    objname_seen = true;
                    section = Section::ObjName;
                    if t.len() == 2 {
                        check_name(t[1])?;
                        objname = Some(t[1].to_owned());
                    }
                }
                "ROWS"
                    if matches!(section, Section::Name | Section::Sense | Section::ObjName)
                        && t.len() == 1 =>
                {
                    if (sense_seen && !sense_value) || (objname_seen && objname.is_none()) {
                        return Err(fail("missing objective header value"));
                    }
                    section = Section::Rows;
                }
                "COLUMNS" if section == Section::Rows && t.len() == 1 => section = Section::Columns,
                "RHS" if section == Section::Columns && !seen_rhs && t.len() == 1 => {
                    seen_rhs = true;
                    section = Section::Rhs;
                }
                "RANGES"
                    if matches!(section, Section::Columns | Section::Rhs)
                        && !seen_ranges
                        && t.len() == 1 =>
                {
                    seen_ranges = true;
                    section = Section::Ranges;
                }
                "BOUNDS"
                    if matches!(section, Section::Columns | Section::Rhs | Section::Ranges)
                        && !seen_bounds
                        && t.len() == 1 =>
                {
                    seen_bounds = true;
                    section = Section::Bounds;
                }
                "ENDATA"
                    if matches!(
                        section,
                        Section::Columns | Section::Rhs | Section::Ranges | Section::Bounds
                    ) && t.len() == 1 =>
                {
                    section = Section::End
                }
                _ => return Err(fail("unknown, misplaced, repeated, or malformed section")),
            }
            continue;
        }
        reject_embedded_fixed_names(line, section, &var_ids).map_err(|e| fail(&e))?;
        match section {
            Section::Sense if t.len() == 1 && !sense_value => {
                maximize = parse_sense(t[0])?;
                sense_value = true;
            }
            Section::ObjName if t.len() == 1 && objname.is_none() => {
                check_name(t[0])?;
                objname = Some(t[0].to_owned());
            }
            Section::Rows => {
                if t.len() != 2 || !matches!(t[0], "N" | "E" | "L" | "G") {
                    return Err(fail("invalid ROWS record"));
                }
                if rows.len() >= MAX_ROWS {
                    return Err(resource("MPS row budget"));
                }
                check_name(t[1])?;
                row_ids
                    .try_reserve(1)
                    .map_err(|_| resource("MPS row-index allocation"))?;
                if row_ids.insert(t[1].to_owned(), rows.len()).is_some() {
                    return Err(fail("duplicate row"));
                }
                push(
                    &mut rows,
                    RawRow {
                        kind: t[0].chars().next().unwrap(),
                        name: t[1].to_owned(),
                        expr: Expr::zero(),
                        rhs: None,
                        range: None,
                    },
                )?;
            }
            Section::Columns => {
                if t.len() == 3 && t[1] == "'MARKER'" {
                    match t[2] {
                        "'INTORG'" if !in_integer => in_integer = true,
                        "'INTEND'" if in_integer => in_integer = false,
                        _ => return Err(fail("invalid or unmatched integer marker")),
                    }
                    last_column = None;
                    continue;
                }
                // Fixed-format blank column-name continuation. Do not infer
                // continuations from arbitrary malformed free-format cards.
                let continuation = matches!(t.len(), 2 | 4)
                    && line.len() >= 14
                    && line[..14].bytes().all(|c| c == b' ');
                let column = if continuation {
                    last_column
                        .as_deref()
                        .ok_or_else(|| fail("column continuation without predecessor"))?
                } else {
                    if !matches!(t.len(), 3 | 5) {
                        return Err(fail("invalid COLUMNS record"));
                    }
                    t[0]
                };
                check_name(column)?;
                let id = if let Some(id) = var_ids.get(column).copied() {
                    if last_column.as_deref() != Some(column) || vars[id].integer != in_integer {
                        return Err(fail("noncontiguous column or changed integrality"));
                    }
                    id
                } else {
                    if vars.len() >= MAX_VARS {
                        return Err(resource("MPS variable budget"));
                    }
                    let id = vars.len();
                    var_ids
                        .try_reserve(1)
                        .map_err(|_| resource("MPS variable-index allocation"))?;
                    var_ids.insert(column.to_owned(), id);
                    push(
                        &mut vars,
                        Var {
                            name: column.to_owned(),
                            integer: in_integer,
                            lower: Some(Q::zero()),
                            upper: if in_integer { Some(Q::one()) } else { None },
                        },
                    )?;
                    push(&mut bounds, BoundState::default())?;
                    id
                };
                let start = usize::from(!continuation);
                for pair in t[start..].chunks_exact(2) {
                    let row = row_ids
                        .get(pair[0])
                        .copied()
                        .ok_or_else(|| fail("unknown coefficient row"))?;
                    let q = parse_q(pair[1]).map_err(|e| fail(&e))?;
                    entries += 1;
                    if entries > MAX_TERMS {
                        return Err(resource("MPS coefficient budget"));
                    }
                    if !q.is_zero() {
                        push(&mut rows[row].expr.terms, (id as u32, q))?;
                    }
                }
                if !continuation {
                    last_column = Some(column.to_owned());
                }
            }
            Section::Rhs | Section::Ranges => {
                let vecname = if section == Section::Rhs {
                    &mut rhs_name
                } else {
                    &mut range_name
                };
                let continuation = matches!(t.len(), 2 | 4)
                    && line.len() >= 14
                    && line[..14].bytes().all(|c| c == b' ');
                if continuation {
                    if vecname.is_none() {
                        return Err(fail("vector continuation without predecessor"));
                    }
                } else {
                    if !matches!(t.len(), 3 | 5) {
                        return Err(fail("invalid RHS/RANGES record"));
                    }
                    check_name(t[0])?;
                    if vecname.as_ref().is_some_and(|name| name != t[0]) {
                        return Err(fail("multiple RHS/range vectors unsupported"));
                    }
                    *vecname = Some(t[0].to_owned());
                }
                for pair in t[usize::from(!continuation)..].chunks_exact(2) {
                    let id = row_ids
                        .get(pair[0])
                        .copied()
                        .ok_or_else(|| fail("unknown RHS/range row"))?;
                    let q = parse_q(pair[1]).map_err(|e| fail(&e))?;
                    if section == Section::Ranges && rows[id].kind == 'N' {
                        return Err(fail("range on objective row"));
                    }
                    let slot = if section == Section::Rhs {
                        &mut rows[id].rhs
                    } else {
                        &mut rows[id].range
                    };
                    if slot.is_some() {
                        return Err(fail("duplicate RHS/range row value"));
                    }
                    *slot = Some(q);
                }
            }
            Section::Bounds => {
                if !matches!(t.len(), 3 | 4) {
                    return Err(fail("invalid BOUNDS record"));
                }
                check_name(t[1])?;
                if bound_name.as_ref().is_some_and(|name| name != t[1]) {
                    return Err(fail("multiple bound vectors unsupported"));
                }
                bound_name = Some(t[1].to_owned());
                let id = var_ids
                    .get(t[2])
                    .copied()
                    .ok_or_else(|| fail("bound on unknown variable"))?;
                let b = &mut bounds[id];
                b.seen = true;
                let q = if t.len() == 4 {
                    Some(parse_q(t[3]).map_err(|e| fail(&e))?)
                } else {
                    None
                };
                match t[0] {
                    "LO" | "LI" | "UP" | "UI" | "FX" => {
                        let q = q.ok_or_else(|| fail("bound value missing"))?;
                        if matches!(t[0], "LI" | "UI") {
                            if !q.is_integer() {
                                return Err(fail("LI/UI bound must be integral"));
                            }
                            vars[id].integer = true;
                        }
                        if matches!(t[0], "LO" | "LI" | "FX") {
                            set_bound(&mut b.lower, Some(q.clone())).map_err(|e| fail(&e))?;
                        }
                        if matches!(t[0], "UP" | "UI" | "FX") {
                            set_bound(&mut b.upper, Some(q)).map_err(|e| fail(&e))?;
                        }
                    }
                    "FR" | "MI" | "PL" => {
                        if q.is_some() {
                            return Err(fail("valueless bound has value"));
                        }
                        if matches!(t[0], "FR" | "MI") {
                            set_bound(&mut b.lower, None).map_err(|e| fail(&e))?;
                        }
                        if matches!(t[0], "FR" | "PL") {
                            set_bound(&mut b.upper, None).map_err(|e| fail(&e))?;
                        }
                    }
                    "BV" => {
                        if q.as_ref().is_some_and(|q| q != &Q::one()) {
                            return Err(fail("BV value must be absent or one"));
                        }
                        b.binary = true;
                        vars[id].integer = true;
                    }
                    _ => return Err(fail("unsupported bound type")),
                }
            }
            _ => return Err(fail("unexpected data record")),
        }
    }
    if section != Section::End {
        return Err("MPS missing ENDATA".into());
    }
    let nrows: Vec<usize> = rows
        .iter()
        .enumerate()
        .filter(|(_, r)| r.kind == 'N')
        .map(|(i, _)| i)
        .collect();
    if nrows.len() != 1 {
        return Err("MPS requires exactly one N objective row".into());
    }
    let objective_id = nrows[0];
    if objname
        .as_ref()
        .is_some_and(|name| name != &rows[objective_id].name)
    {
        return Err("OBJNAME does not select the N row".into());
    }
    for (v, b) in vars.iter_mut().zip(bounds) {
        if b.seen {
            // Integer-marker defaults apply only when the variable has no
            // explicit bound card. LI alone consequently means [LI,+infinity).
            v.lower = b.lower.clone().unwrap_or_else(|| {
                if b.upper
                    .as_ref()
                    .and_then(|q| q.as_ref())
                    .is_some_and(|q| q.is_negative())
                {
                    None
                } else {
                    Some(Q::zero())
                }
            });
            v.upper = b.upper.unwrap_or(None);
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
    let mut model = Model {
        name,
        vars,
        rows: Vec::new(),
        objective: Expr::zero(),
    };
    for (id, mut row) in rows.into_iter().enumerate() {
        row.expr.canonicalize()?;
        let rhs = row.rhs.unwrap_or_else(Q::zero);
        if id == objective_id {
            row.expr.constant = -rhs;
            model.objective = if maximize {
                row.expr.scaled(&-Q::one())?
            } else {
                row.expr
            };
            continue;
        }
        let (lower, upper) = match (row.kind, row.range) {
            ('E', None) => (Some(rhs.clone()), Some(rhs)),
            ('L', None) => (None, Some(rhs)),
            ('G', None) => (Some(rhs), None),
            ('L', Some(r)) => (Some(&rhs - r.abs()), Some(rhs)),
            ('G', Some(r)) => (Some(rhs.clone()), Some(rhs + r.abs())),
            ('E', Some(r)) if r.is_negative() => (Some(&rhs + r), Some(rhs)),
            ('E', Some(r)) => (Some(rhs.clone()), Some(rhs + r)),
            _ => return Err("invalid row kind".into()),
        };
        push(
            &mut model.rows,
            Row {
                name: row.name,
                expr: row.expr,
                lower,
                upper,
            },
        )?;
    }
    model.validate()?;
    Ok(model)
}

fn parse_sense(s: &str) -> Result<bool, String> {
    match s {
        "MIN" | "MINIMIZE" => Ok(false),
        "MAX" | "MAXIMIZE" => Ok(true),
        _ => Err("unsupported OBJSENSE".into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn q(s: &str) -> Q {
        parse_q(s).unwrap()
    }
    fn mps(bounds: &str) -> String {
        format!("NAME tiny\nROWS\n N obj\n L c\nCOLUMNS\n x obj 0.1 c 2\nRHS\n rhs c 3 obj -7\nBOUNDS\n{bounds}ENDATA\n")
    }
    #[test]
    fn exact_numbers_and_budget() {
        assert_eq!(q(".1"), Q::new(1.into(), 10.into()));
        assert_eq!(q("-12.34D-2"), q("-617/5000"));
        assert_eq!(q("+001.200e+2"), q("120"));
        assert_eq!(q("1/-2"), q("-0.5"));
        assert_eq!(q("0.000"), Q::zero());
        for text in [
            "", ".", "+", "NaN", "inf", "1/0", "1/2/3", "1 e3", "1e", "1ee2", "1.2.3",
        ] {
            assert!(parse_q(text).is_err(), "{text}");
        }
        assert!(parse_q("1e2147483648")
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT"));
        assert!(parse_q(&"9".repeat(MAX_DECIMAL_DIGITS + 1)).is_err());
        assert_eq!(
            q("9007199254740993"),
            Q::from_integer(BigInt::from(9007199254740993u64))
        );
    }
    #[test]
    fn objective_offset_and_maximize() {
        let text = mps(" UP b x 10\n");
        let m = parse_mps(&text).unwrap();
        assert_eq!(m.objective.constant, q("7"));
        assert_eq!(m.objective.terms, vec![(0, q("1/10"))]);
        let max = text.replace("ROWS\n", "OBJSENSE\n MAX\nROWS\n");
        let m = parse_mps(&max).unwrap();
        assert_eq!(m.objective.constant, q("-7"));
        assert_eq!(m.objective.terms, vec![(0, q("-1/10"))]);
    }
    #[test]
    fn binary_bounds_are_intersections() {
        for bounds in [" BV b x\n LO b x 2\n", " LO b x 2\n BV b x\n"] {
            let m = parse_mps(&mps(bounds)).unwrap();
            assert!(m.vars[0].integer);
            assert_eq!(m.vars[0].lower, Some(q("2")));
            assert_eq!(m.vars[0].upper, Some(q("1")));
        }
        let m = parse_mps(&mps(" FR b x\n BV b x\n")).unwrap();
        assert_eq!(
            (m.vars[0].lower.clone(), m.vars[0].upper.clone()),
            (Some(q("0")), Some(q("1")))
        );
        let m = parse_mps(&mps(" BV b x\n UP b x -1\n")).unwrap();
        assert_eq!(m.vars[0].lower, Some(q("0")));
        assert_eq!(m.vars[0].upper, Some(q("-1")));
    }
    #[test]
    fn integer_marker_defaults_and_explicit_bounds() {
        let text = mps("")
            .replace(" x obj", " m1 'MARKER' 'INTORG'\n x obj")
            .replace("RHS\n", " m2 'MARKER' 'INTEND'\nRHS\n");
        let m = parse_mps(&text).unwrap();
        assert!(m.vars[0].integer);
        assert_eq!(m.vars[0].upper, Some(q("1")));
        let text = text.replace("BOUNDS\n", "BOUNDS\n LI b x 2\n");
        let m = parse_mps(&text).unwrap();
        assert_eq!(m.vars[0].lower, Some(q("2")));
        assert_eq!(m.vars[0].upper, None);
        for (card, lower) in [(" PL b x\n", Some(q("0"))), (" FR b x\n", None)] {
            let replacement = text.replace(" LI b x 2\n", card);
            let m = parse_mps(&replacement).unwrap();
            assert!(m.vars[0].integer);
            assert_eq!(m.vars[0].lower, lower);
            assert_eq!(m.vars[0].upper, None);
        }
    }
    #[test]
    fn negative_upper_default_lower_and_contradiction() {
        let m = parse_mps(&mps(" UP b x -1\n")).unwrap();
        assert_eq!(m.vars[0].lower, None);
        let m = parse_mps(&mps(" LO b x 0\n UP b x -1\n")).unwrap();
        assert_eq!(m.vars[0].lower, Some(q("0")));
        assert!(m.validate().is_ok());
    }
    #[test]
    fn range_sign_semantics() {
        for (kind, range, lo, hi) in [
            ("L", "-2", "1", "3"),
            ("G", "-2", "3", "5"),
            ("E", "-2", "1", "3"),
            ("E", "2", "3", "5"),
        ] {
            let text = mps("")
                .replace(" L c", &format!(" {kind} c"))
                .replace("BOUNDS\n", &format!("RANGES\n r c {range}\nBOUNDS\n"));
            let m = parse_mps(&text).unwrap();
            assert_eq!(m.rows[0].lower, Some(q(lo)));
            assert_eq!(m.rows[0].upper, Some(q(hi)));
        }
    }
    #[test]
    fn fixed_continuation_and_repeated_coefficients() {
        let text = "NAME fixed\nROWS\n N OBJ\n E C\nCOLUMNS\n    X         OBJ       1\n              C         2\n              C         -1\nRHS\n    RHS       C         3\nENDATA\n";
        let m = parse_mps(text).unwrap();
        assert_eq!(m.rows[0].expr.terms, vec![(0, q("1"))]);
        let continued_rhs = text.replace(
            "    RHS       C         3",
            "    RHS       OBJ       -4\n              C         3",
        );
        let m = parse_mps(&continued_rhs).unwrap();
        assert_eq!(m.objective.constant, q("4"));
        assert_eq!(m.rows[0].lower, Some(q("3")));
        assert!(
            parse_mps(&text.replace("    RHS       C         3", "              C         3"))
                .is_err()
        );
        assert!(
            parse_mps(&text.replace("    X         OBJ       1", "              OBJ       1"))
                .is_err()
        );
    }
    #[test]
    fn fixed_free_ambiguity_regressions() {
        // Real corpus free cards can coincidentally share fixed-format gaps.
        let text = mps(" LO bnd  x  1104\n");
        assert_eq!(parse_mps(&text).unwrap().vars[0].lower, Some(q("1104")));
        let text = mps(" LO bnd  x  0\n");
        assert_eq!(parse_mps(&text).unwrap().vars[0].lower, Some(q("0")));
        // An embedded-space fixed column name must not become two free pairs.
        let text = format!(
            "NAME ambiguous\nROWS\n N OBJ\n E 1\n E C\nCOLUMNS\n    {:8}  {:8}  {:12}\nENDATA\n",
            "X 1 2", "C", "3"
        );
        assert!(parse_mps(&text).unwrap_err().contains("embedded-space"));
    }
    #[test]
    fn unsupported_and_malformed_mps_rejected() {
        let valid = mps(" UP b x 10\n");
        for text in [
            valid.replace("ENDATA", "SOS\nENDATA"),
            valid.replace(" UP b x 10", " SC b x 10"),
            valid.replace("ENDATA", ""),
            valid.clone() + " BOO x\n",
            valid.replace(" L c", " N c"),
            valid.replace("RHS\n", "RHS\n rhs2 c 4\n"),
            valid.replace(" UP b x 10", " UP b x 10\n UP b x 11"),
            valid.replace("RHS\n", " m 'MARKER' 'INTORG'\nRHS\n"),
        ] {
            assert!(parse_mps(&text).is_err(), "accepted malformed MPS: {text}");
        }
    }
    #[test]
    fn validates_canonical_expr_and_rational() {
        let mut e = Expr {
            constant: Q::zero(),
            terms: vec![(1, q("3")), (0, q("2")), (1, q("-3"))],
        };
        assert!(e.validate(2).is_err());
        e.canonicalize().unwrap();
        assert_eq!(e.terms, vec![(0, q("2"))]);
        assert!(e.validate(1).is_ok());
        assert!(check_q(&Q::new_raw(2.into(), 2.into())).is_err());
        assert!(check_q(&Q::new_raw(1.into(), 0.into())).is_err());
        let huge = Q::from_integer(BigInt::one() << (MAX_Q_BITS as usize));
        assert!(check_q(&huge).is_err());
    }
    #[test]
    fn constant_models_and_unknown_json_fields() {
        let m = parse_mps(
            "NAME\nROWS\n N OBJ\n E IMPOSSIBLE\nCOLUMNS\nRHS\n RHS OBJ -2 IMPOSSIBLE 1\nENDATA\n",
        )
        .unwrap();
        assert_eq!(m.name, "MODEL");
        assert!(m.vars.is_empty());
        assert_eq!(m.objective.constant, q("2"));
        assert!(m.rows[0].expr.terms.is_empty());
        assert_eq!(m.rows[0].lower, Some(q("1")));
        assert!(
            serde_json::from_str::<Expr>(r#"{"constant":"0","terms":[],"ignored":true}"#).is_err()
        );
    }
    #[test]
    fn resources_keep_resource_status() {
        let text = mps("").replace("obj 0.1", "obj 1e999999");
        assert!(parse_mps(&text).unwrap_err().starts_with("RESOURCE_LIMIT"));
        assert!(parse_mps(&mps(" LI b x 1.5\n")).is_err());
    }
    #[test]
    fn deterministic_mps_mutations_do_not_panic() {
        let seed = mps(" BV b x\n").into_bytes();
        let mut state = 0x5250584d505331u64;
        for case in 0..2000 {
            let mut bytes = seed.clone();
            for _ in 0..=case % 7 {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                let id = (state as usize) % bytes.len();
                bytes[id] = (state >> 32) as u8 & 0x7f;
            }
            let text = String::from_utf8(bytes).unwrap();
            let result = std::panic::catch_unwind(|| parse_mps(&text));
            assert!(result.is_ok(), "panic in deterministic MPS mutation {case}");
            // Some mutations are valid changes; do not require rejection.
            if let Ok(model) = result.unwrap() {
                model.validate().unwrap();
            }
        }
    }
}
