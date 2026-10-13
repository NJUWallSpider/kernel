//! Exact supplementary point checks, including V10 draft image exclusion.
//!
//! `verify_points` checks witnesses and their requested point claims. The full
//! verifier must first prove all requested mapping claims. A separating point
//! alone does not establish the inclusion half of strict inclusion.
use crate::build_support::Support;
const SUPPORT: Support = Support::new("point");
use crate::model::{check_q, Expr, Model, Row, MAX_ROWS, MAX_TERMS, Q};
use crate::proof::{Block, Certificate, PointClaim, Request};
use crate::verify::Limits;
use num_traits::{One, Zero};
use serde::Serialize;

pub const MAX_POINT_WITNESSES: usize = 1_000_000;
pub const MAX_POINT_VALUES: usize = MAX_TERMS;

fn invalid(s: &str) -> String {
    format!("INVALID point: {s}")
}
fn resource(s: &str) -> String {
    format!("RESOURCE_LIMIT point: {s}")
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct PointStatistics {
    pub points: u64,
    pub coefficient_terms: u64,
    pub work: u64,
}

struct Checker<'a> {
    limits: &'a Limits,
    statistics: PointStatistics,
}
enum Coordinates<'a> {
    Direct(&'a [Q]),
    /// Input coordinate i obtains the same output point's coordinate index[i].
    Projected {
        values: &'a [Q],
        index: &'a [usize],
    },
}
impl Coordinates<'_> {
    fn len(&self) -> usize {
        match self {
            Self::Direct(v) => v.len(),
            Self::Projected { index, .. } => index.len(),
        }
    }
    fn get(&self, id: usize) -> Result<&Q, String> {
        match self {
            Self::Direct(v) => v.get(id),
            Self::Projected { values, index } => index.get(id).and_then(|i| values.get(*i)),
        }
        .ok_or_else(|| invalid("coordinate outside complete witness"))
    }
}
impl Checker<'_> {
    fn charge(&mut self, n: usize) -> Result<(), String> {
        SUPPORT.charge(&mut self.statistics.work, self.limits.work, n, "arithmetic work budget")
    }
    fn evaluate(&mut self, expr: &Expr, point: &Coordinates<'_>) -> Result<Q, String> {
        self.charge(1)?;
        check_q(&expr.constant)?;
        let mut sum = expr.constant.clone();
        for (id, coefficient) in &expr.terms {
            self.charge(2)?;
            self.statistics.coefficient_terms = self
                .statistics
                .coefficient_terms
                .checked_add(1)
                .ok_or_else(|| resource("coefficient counter overflow"))?;
            // Model data and coordinates were validated. Every temporary
            // product and partial sum is checked before it can affect a result.
            let product = coefficient * point.get(*id as usize)?;
            check_q(&product)?;
            sum += product;
            check_q(&sum)?;
        }
        Ok(sum)
    }
    /// Early exit is sound for rejection or a separating witness; all point
    /// coordinates and all model scalars have already been validated.
    fn feasible(
        &mut self,
        model: &Model,
        point: &Coordinates<'_>,
        integers: bool,
    ) -> Result<bool, String> {
        if point.len() != model.vars.len() {
            return Err(invalid("point dimension differs from model"));
        }
        for (id, var) in model.vars.iter().enumerate() {
            self.charge(1)?;
            let value = point.get(id)?;
            if var.lower.as_ref().is_some_and(|lower| value < lower)
                || var.upper.as_ref().is_some_and(|upper| value > upper)
                || (integers && var.integer && !value.is_integer())
            {
                return Ok(false);
            }
        }
        for row in &model.rows {
            let value = self.evaluate(&row.expr, point)?;
            self.charge(1)?;
            if row.lower.as_ref().is_some_and(|lower| &value < lower)
                || row.upper.as_ref().is_some_and(|upper| &value > upper)
            {
                return Ok(false);
            }
        }
        Ok(true)
    }
    /// A caller-bound image exclusion is a statement about one complete LP
    /// point and one complete affine image. It needs no global inclusion map
    /// and establishes neither containment nor an objective comparison.
    fn image_exclusion(
        &mut self,
        source: &Model,
        target: &Model,
        point_in_target: bool,
        map: &[Expr],
        values: &[Q],
    ) -> Result<(), String> {
        let (input, output) = if point_in_target {
            (target, source)
        } else {
            (source, target)
        };
        if values.len() != input.vars.len() {
            return Err(invalid("image exclusion point dimension"));
        }
        if map.len() != output.vars.len() {
            return Err(invalid("image exclusion map dimension"));
        }
        // Validate every expression before any early separation result. No
        // coordinate may refer to an extension or the opposite model's scope.
        let mut terms = 0usize;
        for expression in map {
            terms = SUPPORT.add(terms, expression.terms.len())?;
            if terms > MAX_TERMS {
                return Err(resource("image exclusion map terms"));
            }
            self.charge(SUPPORT.add(expression.terms.len(), 1)?)?;
            expression.validate(input.vars.len())?;
        }
        let point = Coordinates::Direct(values);
        if !self.feasible(input, &point, false)? {
            return Err(invalid("image exclusion witness is not LP feasible"));
        }
        self.charge(map.len())?;
        let mut image = SUPPORT.reserved(map.len())?;
        for expression in map {
            image.push(self.evaluate(expression, &point)?);
        }
        // LP feasibility deliberately ignores integrality on both sides. A
        // fractional image alone is not an actual bound/row violation.
        if self.feasible(output, &Coordinates::Direct(&image), false)? {
            return Err(invalid("image exclusion violates no actual output bound or row"));
        }
        Ok(())
    }
    fn strictness(
        &mut self,
        source: &Model,
        target: &Model,
        certificate: &Certificate,
        index: u32,
        values: &[Q],
    ) -> Result<(), String> {
        let claim = certificate
            .claims
            .get(index as usize)
            .ok_or_else(|| invalid("strictness inclusion claim index"))?;
        if claim.input_objective_level.is_some(){return Err(invalid("strictness requires unrestricted inclusion domain"));}
        if claim.input_integers || claim.output_integers {
            return Err(invalid("strictness requires an LP-to-LP inclusion claim"));
        }
        let (input, output) = if claim.reverse {
            (target, source)
        } else {
            (source, target)
        };
        let n = input.vars.len();
        if output.vars.len() != n || claim.projection.len() != n {
            return Err(invalid(
                "strictness requires a projection covering every coordinate on both sides",
            ));
        }
        if values.len() != n {
            return Err(invalid("strictness point dimension"));
        }
        self.charge(n)?;
        let mut inverse = Vec::new();
        inverse
            .try_reserve_exact(n)
            .map_err(|_| resource("projection index allocation"))?;
        inverse.resize(n, usize::MAX);
        let mut seen = Vec::new();
        seen.try_reserve_exact(n)
            .map_err(|_| resource("projection uniqueness allocation"))?;
        seen.resize(n, false);
        for &(i, o) in &claim.projection {
            let (i, o) = (i as usize, o as usize);
            if i >= n || o >= n || inverse[i] != usize::MAX || seen[o] {
                return Err(invalid(
                    "strictness projection is not a complete coordinate bijection",
                ));
            }
            inverse[i] = o;
            seen[o] = true;
        }
        if inverse.contains(&usize::MAX) || seen.contains(&false) {
            return Err(invalid("incomplete strictness projection"));
        }
        if !self.feasible(output, &Coordinates::Direct(values), false)? {
            return Err(invalid(
                "strictness witness is not feasible in the inclusion output LP",
            ));
        }
        let reconstructed = Coordinates::Projected {
            values,
            index: &inverse,
        };
        if self.feasible(input, &reconstructed, false)? {
            return Err(invalid(
                "strictness witness violates no actual inclusion input bound or row",
            ));
        }
        Ok(())
    }

    /// A complete output point separates a projection only if the entire input
    /// fiber, including ALL coordinate and affine observations, is refuted.
    fn fiber_strictness(
        &mut self,
        source: &Model,
        target: &Model,
        certificate: &Certificate,
        index: u32,
        values: &[Q],
        refutation: &Block,
    ) -> Result<(), String> {
        let claim = certificate
            .claims
            .get(index as usize)
            .ok_or_else(|| invalid("fiber strictness inclusion claim index"))?;
        if claim.input_objective_level.is_some(){return Err(invalid("strictness requires unrestricted inclusion domain"));}
        if claim.input_integers || claim.output_integers {
            return Err(invalid(
                "fiber strictness requires an LP-to-LP inclusion claim",
            ));
        }
        let (input, output) = if claim.reverse {
            (target, source)
        } else {
            (source, target)
        };
        let point = Coordinates::Direct(values);
        if !self.feasible(output, &point, false)? {
            return Err(invalid(
                "fiber strictness witness is not feasible in the inclusion output LP",
            ));
        }

        let observations = SUPPORT.add(claim.projection.len(), claim.affine_projection.len())?;
        let rows = SUPPORT.add(input.rows.len(), observations)?;
        if rows > MAX_ROWS {
            return Err(resource("fiber row count"));
        }
        // Validate against the original directional models, before appending
        // any fiber rows. In particular, observations cannot name new symbols.
        let (mut terms, mut copy_work) = SUPPORT.model_size(input)?;
        for &(i, o) in &claim.projection {
            if i as usize >= input.vars.len() || o as usize >= output.vars.len() {
                return Err(invalid("fiber projection coordinate"));
            }
            terms = SUPPORT.add(terms, 1)?;
            copy_work = SUPPORT.add(copy_work, 33)?;
        }
        for (input_expr, output_expr) in &claim.affine_projection {
            self.charge(SUPPORT.add(input_expr.terms.len(), output_expr.terms.len())?)?;
            input_expr.validate(input.vars.len())?;
            output_expr.validate(output.vars.len())?;
            terms = SUPPORT.add(terms, input_expr.terms.len())?;
            copy_work = SUPPORT.add(copy_work, SUPPORT.add(input_expr.terms.len(), 32)?)?;
        }
        if terms > MAX_TERMS {
            return Err(resource("fiber model term count"));
        }
        self.charge(
            copy_work
                .checked_mul(2)
                .ok_or_else(|| resource("fiber work count"))?,
        )?;
        let mut fiber = SUPPORT.copy_prefix(input, input.vars.len(), rows)?;
        let mut names = SUPPORT.names(input.rows.iter().map(|row| row.name.as_str()),
            input.rows.len(), "$rpx_fiber_row_")?;
        let mut append = |checker: &mut Self, expression: Expr, value: Q| -> Result<(), String> {
            let name = names.fresh_with(|n| checker.charge(n))?;
            fiber.rows.push(Row {
                name,
                expr: expression,
                lower: Some(value.clone()),
                upper: Some(value),
            });
            Ok(())
        };
        for &(i, o) in &claim.projection {
            self.charge(1)?;
            let mut terms = SUPPORT.reserved(1)?;
            terms.push((i, Q::one()));
            append(
                self,
                Expr {
                    constant: Q::zero(),
                    terms,
                },
                point.get(o as usize)?.clone(),
            )?;
        }
        for (input_expr, output_expr) in &claim.affine_projection {
            let value = self.evaluate(output_expr, &point)?;
            append(self, SUPPORT.copy_expr(input_expr)?, value)?;
        }
        if fiber.rows.len() != rows {
            return Err(invalid("internal fiber row layout"));
        }
        let remaining = Limits {
            work: self
                .limits
                .work
                .checked_sub(self.statistics.work)
                .ok_or_else(|| resource("fiber remaining work"))?,
            live_facts: self.limits.live_facts,
            depth: self.limits.depth,
        };
        // This entry point starts with no map-proof facts or branch assumptions,
        // permits only Absurd/Split endpoints, and disables integer declarations.
        let statistics = crate::verify::verify_lp_refutation(&fiber, refutation, &remaining)?;
        self.charge(
            usize::try_from(statistics.work)
                .map_err(|_| resource("fiber refutation work width"))?,
        )?;
        Ok(())
    }
}

/// Verify requested exact feasibility/separation witnesses after the mapping
/// checker has established every claim. Returns bounded supplementary work;
/// `verify_request` supplies the remaining request-wide arithmetic budget.
pub fn verify_points(
    source: &Model,
    target: &Model,
    certificate: &Certificate,
    requested: &Request,
    limits: &Limits,
) -> Result<PointStatistics, String> {
    if certificate.claims != requested.claims
        || certificate.points.len() != requested.points.len()
        || certificate
            .points
            .iter()
            .zip(&requested.points)
            .any(|(w, c)| &w.claim != c)
    {
        return Err(invalid("caller-requested point contract mismatch"));
    }
    if certificate.points.len() > MAX_POINT_WITNESSES {
        return Err(resource("point witness count"));
    }
    let mut total = 0usize;
    for witness in &certificate.points {
        total = total
            .checked_add(witness.values.len())
            .ok_or_else(|| resource("coordinate count overflow"))?;
        if total > MAX_POINT_VALUES {
            return Err(resource("total witness coordinates"));
        }
    }
    if certificate.points.is_empty() {
        return Ok(PointStatistics::default());
    }
    // Keep the public helper total even when invoked outside verify_request.
    source.validate()?;
    target.validate()?;
    let mut checker = Checker {
        limits,
        statistics: PointStatistics::default(),
    };
    for (index, witness) in certificate.points.iter().enumerate() {
        checker.charge(1)?;
        checker.charge(witness.values.len())?;
        for q in &witness.values {
            check_q(q)?;
        }
        if !matches!(&witness.claim, PointClaim::FiberStrictness { .. })
            && witness.refutation.is_some()
        {
            return Err(invalid("surplus point refutation"));
        }
        let result = match &witness.claim {
            PointClaim::ImageExclusion { point_in_target, map } => checker.image_exclusion(
                source,
                target,
                *point_in_target,
                map,
                &witness.values,
            ),
            PointClaim::Feasible {
                target: which,
                integers,
                objective,
            } => {
                let model = if *which { target } else { source };
                if let Some(value) = objective {
                    check_q(value)?;
                }
                let point = Coordinates::Direct(&witness.values);
                if !checker.feasible(model, &point, *integers)? {
                    return Err(format!("{} (witness {index})", invalid("infeasible point")));
                }
                if let Some(value) = objective {
                    if checker.evaluate(&model.objective, &point)? != *value {
                        return Err(format!(
                            "{} (witness {index})",
                            invalid("objective value mismatch")
                        ));
                    }
                }
                Ok(())
            }
            PointClaim::Strictness { inclusion_claim } => checker.strictness(
                source,
                target,
                certificate,
                *inclusion_claim,
                &witness.values,
            ),
            PointClaim::FiberStrictness { inclusion_claim } => checker.fiber_strictness(
                source,
                target,
                certificate,
                *inclusion_claim,
                &witness.values,
                witness
                    .refutation
                    .as_ref()
                    .ok_or_else(|| invalid("missing fiber refutation"))?,
            ),
        };
        result.map_err(|e| format!("{e} (witness {index})"))?;
        checker.statistics.points = checker
            .statistics
            .points
            .checked_add(1)
            .ok_or_else(|| resource("point counter overflow"))?;
    }
    Ok(checker.statistics)
}
