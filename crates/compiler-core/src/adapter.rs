//! Explicit exact representation adaptation; no selected theorem or solver.
use crate::{
    error::Error,
    expr,
    model::{Identifier, Model, mps},
    proof::{FactId, ProofCore, ScopeId},
    space::BoundExpr,
};
use kernel_core::model::{Expr, Q, Row, Var, check_q};
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Zero};
use std::{collections::HashSet, sync::Arc};
#[derive(Clone, Debug)]
pub struct StandardMps {
    pub source: Arc<Model>,
    pub target: Arc<Model>,
    scales: Vec<Vec<Q>>,
    moves: Vec<(u32, bool, u32, Vec<Q>)>,
    auxiliary: Option<(u32, u32, Vec<Q>)>,
    pub report: serde_json::Value,
}
fn nondecimal(mut d: BigInt) -> BigInt {
    while d.is_even() {
        d /= 2;
    }
    while (&d % 5u32).is_zero() {
        d /= 5;
    }
    d
}
fn scale(values: &[Q], original: &[Q]) -> Result<(Q, Vec<Q>), Error> {
    let mut scale = BigInt::one();
    for q in values {
        scale = scale.lcm(&nondecimal(q.denom().clone()));
        if scale.bits() > 65536 {
            return Err(Error::Resource(
                "MPS normalization scale exceeds arithmetic limit".into(),
            ));
        }
    }
    let mut remaining = scale.clone();
    let mut chunk = BigInt::one();
    let mut chunks = Vec::new();
    for q in original {
        let factor = remaining.gcd(&nondecimal(q.denom().clone()));
        if factor.bits() > 13600 {
            return Err(Error::Resource(
                "MPS proof factor exceeds RPX scalar limit".into(),
            ));
        }
        remaining /= &factor;
        if factor.is_one() {
            continue;
        }
        if (&chunk * &factor).bits() > 13600 {
            chunks.push(Q::from_integer(chunk));
            chunk = factor;
        } else {
            chunk *= factor;
        }
    }
    if !remaining.is_one() {
        return Err(Error::Invalid(
            "MPS normalization factors do not cover the scale".into(),
        ));
    }
    if !chunk.is_one() {
        chunks.push(Q::from_integer(chunk));
    }
    Ok((Q::from_integer(scale), chunks))
}
fn fresh(base: &str, names: &mut HashSet<String>) -> String {
    let mut name = base.to_string();
    let mut i = 1;
    while names.contains(&name) {
        name = format!("{}_{}", &base[..base.len().min(990)], i);
        i += 1;
    }
    names.insert(name.clone());
    name
}
impl StandardMps {
    pub fn new(
        source: Arc<Model>,
        objective_auxiliary: bool,
        objective_name: &str,
    ) -> Result<Self, Error> {
        let m = &source.inner;
        let mut rows = Vec::new();
        let mut scales = Vec::new();
        let mut records = Vec::new();
        let mut row_names: HashSet<_> = m.rows.iter().map(|r| r.name.clone()).collect();
        let mut var_names: HashSet<_> = m.vars.iter().map(|v| v.name.clone()).collect();
        for r in &m.rows {
            let lower = r.lower.as_ref().map(|q| q - &r.expr.constant);
            let upper = r.upper.as_ref().map(|q| q - &r.expr.constant);
            let mut values: Vec<_> = r.expr.terms.iter().map(|(_, q)| q.clone()).collect();
            values.extend(lower.iter().cloned());
            values.extend(upper.iter().cloned());
            let mut original: Vec<_> = r.expr.terms.iter().map(|(_, q)| q.clone()).collect();
            original.push(r.expr.constant.clone());
            original.extend(r.lower.iter().cloned());
            original.extend(r.upper.iter().cloned());
            let (q, chunks) = scale(&values, &original)?;
            let expression =
                expr::canonical(Q::zero(), r.expr.terms.iter().map(|(i, v)| (*i, v * &q)))?;
            rows.push(Row {
                name: r.name.clone(),
                expr: expression,
                lower: lower.map(|v| v * &q),
                upper: upper.map(|v| v * &q),
            });
            if !q.is_one() {
                records.push(serde_json::json!({"row":r.name,"scale":q.to_string()}));
            }
            scales.push(chunks);
        }
        let mut vars = m.vars.clone();
        let mut moves = Vec::new();
        for (i, v) in vars.iter_mut().enumerate() {
            for lower in [true, false] {
                let bound = if lower { &mut v.lower } else { &mut v.upper };
                if let Some(q) = bound.clone() {
                    if !nondecimal(q.denom().clone()).is_one() {
                        let (s, chunks) = scale(&[q.clone()], &[q.clone()])?;
                        let name = fresh(
                            &format!("__mps_bound_{i}_{}", if lower { "lower" } else { "upper" }),
                            &mut row_names,
                        );
                        let value = &s * &q;
                        moves.push((i as u32, lower, rows.len() as u32, chunks));
                        rows.push(Row {
                            name,
                            expr: Expr::var(i as u32).scaled(&s)?,
                            lower: lower.then_some(value.clone()),
                            upper: (!lower).then_some(value),
                        });
                        *bound = None;
                    }
                }
            }
        }
        let mut objective = m.objective.clone();
        let values: Vec<_> = std::iter::once(objective.constant.clone())
            .chain(objective.terms.iter().map(|(_, q)| q.clone()))
            .collect();
        let mut auxiliary = None;
        if values
            .iter()
            .any(|q| !nondecimal(q.denom().clone()).is_one())
        {
            if !objective_auxiliary {
                return Err(Error::Invalid(
                    "objective has a nonterminating decimal; enable objective_auxiliary".into(),
                ));
            }
            for q in &values {
                if q.numer().bits() > 13600 || q.denom().bits() > 13600 {
                    return Err(Error::Resource(
                        "objective map exceeds RPX scalar limit".into(),
                    ));
                }
            }
            let (s, chunks) = scale(&values, &values)?;
            let i = vars.len() as u32;
            let name = fresh(objective_name, &mut var_names);
            let row_name = fresh(&format!("{name}_definition"), &mut row_names);
            vars.push(Var {
                name,
                integer: false,
                lower: None,
                upper: None,
            });
            let mut terms = vec![(i, s.clone())];
            terms.extend(objective.terms.iter().map(|(i, q)| (*i, -q * &s)));
            let value = &s * &objective.constant;
            check_q(&value)?;
            auxiliary = Some((i, rows.len() as u32, chunks));
            rows.push(Row {
                name: row_name,
                expr: expr::canonical(Q::zero(), terms)?,
                lower: Some(value.clone()),
                upper: Some(value),
            });
            objective = Expr::var(i);
        }
        let target = Arc::new(Model::new(m.name.clone(), vars, rows, objective)?);
        let text = mps(&target, false)?;
        let readback = Model::parse(&text, crate::model::ModelFormat::Mps)?;
        if !target.same_formulation(&readback) {
            return Err(Error::Artifact(
                "standard MPS readback differs from target".into(),
            ));
        }
        let report = serde_json::json!({"before":source.stats(),"after":target.stats(),"row_scales":records,"mps_readback":{"status":"MATCHED","bytes":text.len()},"bound_moves":moves.len(),"objective_auxiliary":auxiliary.as_ref().map(|(i,r,_)|serde_json::json!({"variable":target.inner.vars[*i as usize].name,"definition_row":target.inner.rows[*r as usize].name}))});
        Ok(Self {
            source,
            target,
            scales,
            moves,
            auxiliary,
            report,
        })
    }
    pub fn proof(&self) -> Result<ProofCore, Error> {
        let mut p = ProofCore::new(self.source.clone(), self.target.clone())?;
        let f = p.forward;
        let r = p.reverse;
        let extra = self
            .auxiliary
            .as_ref()
            .map(|(i, _, _)| {
                (
                    self.target.inner.vars[*i as usize].name.clone(),
                    BoundExpr::new(
                        self.source.inner.objective.clone(),
                        Some(self.source.space.clone()),
                    ),
                )
            })
            .into_iter()
            .collect();
        p.set_mapping(f, true, extra)?;
        p.set_mapping(r, true, vec![])?;
        for (i, chunks) in self.scales.iter().enumerate() {
            if chunks.is_empty() {
                continue;
            }
            let row = &self.source.inner.rows[i];
            let tags = if row.lower.is_some() && row.lower == row.upper {
                vec!["RowEq"]
            } else {
                let mut tags = vec![];
                if row.lower.is_some() {
                    tags.push("RowLower");
                }
                if row.upper.is_some() {
                    tags.push("RowUpper");
                }
                tags
            };
            for tag in tags {
                let a = p.ref_fact(f, tag, &Identifier::Index(i as u32))?;
                scaled(&mut p, f, a, chunks, false, false)?;
                let b = p.ref_fact(r, tag, &Identifier::Index(i as u32))?;
                scaled(&mut p, r, b, chunks, true, false)?;
            }
        }
        for (i, lower, row, chunks) in &self.moves {
            let a = p.ref_fact(
                f,
                if *lower { "VarLower" } else { "VarUpper" },
                &Identifier::Index(*i),
            )?;
            scaled(&mut p, f, a, chunks, false, false)?;
            let b = p.ref_fact(
                r,
                if *lower { "RowLower" } else { "RowUpper" },
                &Identifier::Index(*row),
            )?;
            scaled(&mut p, r, b, chunks, true, false)?;
        }
        if let Some((_, row, chunks)) = &self.auxiliary {
            let b = p.ref_fact(r, "RowEq", &Identifier::Index(*row))?;
            scaled(&mut p, r, b, chunks, true, true)?;
        }
        p.finish(f)?;
        p.finish(r)?;
        Ok(p)
    }
}
fn scaled(
    p: &mut ProofCore,
    scope: ScopeId,
    mut fact: FactId,
    chunks: &[Q],
    reverse: bool,
    negative: bool,
) -> Result<FactId, Error> {
    let mut factors = chunks.to_vec();
    if reverse {
        factors.reverse();
    }
    if factors.is_empty() && negative {
        return p.eq(scope, &[(fact, -Q::one())], Q::zero(), None);
    }
    for (i, q) in factors.into_iter().enumerate() {
        let mut q = if reverse { q.recip() } else { q };
        if negative && i == 0 {
            q = -q;
        }
        let kind = p.fact(fact)?.kind;
        fact = p.lin(scope, kind, &[(fact, q)], Q::zero(), None)?;
    }
    Ok(fact)
}
