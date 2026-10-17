//! Native proof scope construction over the kernel Certificate data types.
use crate::expr;
use crate::limit::{invalid, resource};
use crate::model::{Identifier, Model};
use kernel_core::model::{Expr, Q, check_q};
use kernel_core::proof::{
    Block, CasesStep, Certificate, Derivation, End, FlowWitness, IntervalWitness, Kind,
    MenuWitness, Ref, SignedWitness, Step, SubflowWitness,
};
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, Zero};
use std::collections::{BTreeMap, BinaryHeap, HashMap, HashSet};
use std::sync::Arc;

pub type ScopeId = usize;
pub type FactId = usize;

#[derive(Clone, Debug)]
pub struct FactData {
    pub kind: Kind,
    pub expression: Expr,
    pub reference: Ref,
    pub scope: ScopeId,
}

#[derive(Clone, Debug)]
pub enum ScopeEnd {
    Return {
        map: Vec<Expr>,
        checks: Vec<Ref>,
    },
    Split {
        expression: Expr,
        integer: Option<Ref>,
        left: ScopeId,
        right: ScopeId,
    },
    Absurd {
        fact: Ref,
    },
    Interval {
        intervals: Vec<IntervalWitness>,
        body: ScopeId,
    },
    Menu {
        menus: Vec<MenuWitness>,
        body: ScopeId,
    },
    Signed {
        decompositions: Vec<SignedWitness>,
        body: ScopeId,
    },
    Flow {
        witness: FlowWitness,
        body: ScopeId,
    },
    Subflow {
        witness: SubflowWitness,
        body: ScopeId,
    },
}

#[derive(Clone, Debug)]
pub enum MutationValue {
    Ref(Ref),
    Expr(Expr),
    Step(Step),
    End(End),
    Block(Block),
    Certificate(Certificate),
}

#[derive(Clone, Debug)]
pub struct Scope {
    pub model: Arc<Model>,
    pub output_model: Arc<Model>,
    pub parent: Option<ScopeId>,
    pub assumptions: Vec<FactId>,
    pub steps: Vec<Step>,
    pub end: Option<ScopeEnd>,
    pub children: Option<Vec<ScopeId>>,
    pub facts: HashMap<u32, FactId>,
    pub base: HashMap<(u32, u8), FactId>,
    pub base_all: Option<Vec<FactId>>,
    pub dropped: HashSet<u32>,
    pub revision: u64,
    pub mapping: Option<Vec<Expr>>,
    pub assigned: HashMap<Selector, AssignmentValue>,
    pub generated_variables: Vec<u32>,
    pub generated_rows: Vec<u32>,
    pub layout: Option<Vec<serde_json::Value>>,
    pub layout_kind: Option<&'static str>,
    pub completion: Option<CompletionRequest>,
    pub completed_revisions: Option<Vec<(ScopeId, u64)>>,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Selector {
    Index(usize),
    Label(String),
}

#[derive(Clone, Debug)]
pub enum AssignmentValue {
    Fact(FactId),
    Exact,
}

#[derive(Clone, Debug)]
pub struct CompletionRequest {
    pub scope: ScopeId,
    pub mapping: Vec<Expr>,
    pub witnesses: Vec<(Selector, AssignmentValue)>,
    pub auto: bool,
}

#[derive(Clone, Debug)]
pub struct ProofCore {
    pub source: Arc<Model>,
    pub target: Arc<Model>,
    pub scopes: Vec<Scope>,
    pub facts: Vec<FactData>,
    pub next_local: u32,
    pub forward: ScopeId,
    pub reverse: ScopeId,
}

impl ProofCore {
    pub fn new(source: Model, target: Model) -> Result<Self, String> {
        let source = Arc::new(source);
        let target = Arc::new(target);
        let mut core = Self {
            source: Arc::clone(&source),
            target: Arc::clone(&target),
            scopes: Vec::new(),
            facts: Vec::new(),
            next_local: 0,
            forward: 0,
            reverse: 0,
        };
        core.forward = core.new_scope(Arc::clone(&source), Arc::clone(&target), None, Vec::new());
        core.reverse = core.new_scope(Arc::clone(&target), source, None, Vec::new());
        Ok(core)
    }

    pub fn standalone(model: Model) -> Result<Self, String> {
        let model = Arc::new(model);
        let mut core = Self {
            source: Arc::clone(&model),
            target: Arc::clone(&model),
            scopes: Vec::new(),
            facts: Vec::new(),
            next_local: 0,
            forward: 0,
            reverse: 0,
        };
        core.forward = core.new_scope(Arc::clone(&model), model, None, Vec::new());
        core.reverse = core.forward;
        Ok(core)
    }

    pub fn new_scope(
        &mut self,
        model: Arc<Model>,
        output_model: Arc<Model>,
        parent: Option<ScopeId>,
        assumptions: Vec<FactId>,
    ) -> ScopeId {
        let id = self.scopes.len();
        self.scopes.push(Scope {
            model,
            output_model,
            parent,
            assumptions,
            steps: Vec::new(),
            end: None,
            children: None,
            facts: HashMap::new(),
            base: HashMap::new(),
            base_all: None,
            dropped: HashSet::new(),
            revision: 0,
            mapping: None,
            assigned: HashMap::new(),
            generated_variables: Vec::new(),
            generated_rows: Vec::new(),
            layout: None,
            layout_kind: None,
            completion: None,
            completed_revisions: None,
        });
        id
    }

    pub fn scope(&self, id: ScopeId) -> Result<&Scope, String> {
        self.scopes
            .get(id)
            .ok_or_else(|| invalid("unknown proof scope"))
    }

    pub fn scope_mut(&mut self, id: ScopeId) -> Result<&mut Scope, String> {
        self.scopes
            .get_mut(id)
            .ok_or_else(|| invalid("unknown proof scope"))
    }

    pub fn fact(&self, id: FactId) -> Result<&FactData, String> {
        self.facts
            .get(id)
            .ok_or_else(|| invalid("unknown fact handle"))
    }

    pub fn fact_data(&self, id: FactId) -> Result<FactData, String> {
        self.fact(id).cloned()
    }

    pub fn visible(&self, scope: ScopeId, fact_id: FactId) -> Result<(), String> {
        let fact = self.fact(fact_id)?;
        let mut current = Some(scope);
        while let Some(id) = current {
            let item = self.scope(id)?;
            if let Ref::Local(local) = fact.reference {
                if item.dropped.contains(&local) {
                    return Err(invalid("local fact was dropped in this proof scope"));
                }
            }
            if id == fact.scope {
                break;
            }
            current = item.parent;
        }
        if current.is_none() {
            return Err(invalid(
                "fact belongs to a sibling or unrelated proof scope",
            ));
        }
        if let Ref::Local(local) = fact.reference {
            if self.scope(fact.scope)?.facts.get(&local) != Some(&fact_id) {
                return Err(invalid("local fact was dropped or is unavailable"));
            }
        }
        if matches!(fact.reference, Ref::Exact) {
            return Err(invalid(
                "Exact is a terminal witness and cannot be a rule premise",
            ));
        }
        Ok(())
    }

    pub fn ensure_base(&mut self, scope: ScopeId) -> Result<(), String> {
        if self.scope(scope)?.base_all.is_some() {
            return Ok(());
        }
        let model = self.scope(scope)?.model.clone();
        let mut facts = Vec::new();
        for (index, variable) in model.inner.vars.iter().enumerate() {
            let index = index as u32;
            if variable.lower.is_some() {
                facts.push(self.make_base_fact(scope, "VarLower", index)?);
            }
            if variable.upper.is_some() {
                facts.push(self.make_base_fact(scope, "VarUpper", index)?);
            }
            if variable.integer {
                facts.push(self.make_base_fact(scope, "VarInt", index)?);
            }
        }
        for (index, row) in model.inner.rows.iter().enumerate() {
            let index = index as u32;
            if row.lower.is_some() && row.lower == row.upper {
                facts.push(self.make_base_fact(scope, "RowEq", index)?);
            } else {
                if row.lower.is_some() {
                    facts.push(self.make_base_fact(scope, "RowLower", index)?);
                }
                if row.upper.is_some() {
                    facts.push(self.make_base_fact(scope, "RowUpper", index)?);
                }
            }
        }
        self.scope_mut(scope)?.base_all = Some(facts);
        Ok(())
    }

    fn make_base_fact(&mut self, scope: ScopeId, kind: &str, index: u32) -> Result<FactId, String> {
        let model = self.scope(scope)?.model.clone();
        let identifier = Identifier::Index(index);
        let (actual_kind, expression) = model.fact(kind, &identifier)?;
        let reference = model.reference(kind, &identifier)?;
        let fact = self.push_fact(actual_kind, expression, reference, scope);
        self.scope_mut(scope)?
            .base
            .insert((index, fact_tag(kind)), fact);
        Ok(fact)
    }

    pub fn push_fact(
        &mut self,
        kind: Kind,
        expression: Expr,
        reference: Ref,
        scope: ScopeId,
    ) -> FactId {
        let id = self.facts.len();
        self.facts.push(FactData {
            kind,
            expression,
            reference,
            scope,
        });
        id
    }

    pub fn ref_fact(
        &mut self,
        scope: ScopeId,
        kind: &str,
        identifier: &Identifier,
    ) -> Result<FactId, String> {
        let model = self.scope(scope)?.model.clone();
        let row = kind.starts_with("Row");
        let index = model.index(identifier, row)?;
        if let Some(fact) = self.scope(scope)?.base.get(&(index, fact_tag(kind))) {
            return Ok(*fact);
        }
        let (actual_kind, expression) = model.fact(kind, identifier)?;
        let reference = model.reference(kind, identifier)?;
        let fact = self.push_fact(actual_kind, expression, reference, scope);
        self.scope_mut(scope)?
            .base
            .insert((index, fact_tag(kind)), fact);
        Ok(fact)
    }

    pub fn register(
        &mut self,
        scope: ScopeId,
        kind: Kind,
        expression: Expr,
        step: Step,
    ) -> Result<FactId, String> {
        expression.validate(self.scope(scope)?.model.inner.vars.len())?;
        if !matches!(kind, Kind::Le | Kind::Eq | Kind::Int) {
            return Err(invalid("unknown fact kind"));
        }
        let id = self.next_local;
        self.next_local = self
            .next_local
            .checked_add(1)
            .ok_or_else(|| resource("local fact counter overflow"))?;
        let step = with_step_id(step, id);
        self.scope_mut(scope)?.steps.push(step);
        self.scope_mut(scope)?.revision += 1;
        let fact = self.push_fact(kind, expression, Ref::Local(id), scope);
        self.scope_mut(scope)?.facts.insert(id, fact);
        Ok(fact)
    }

    pub fn lin(
        &mut self,
        scope: ScopeId,
        kind: Kind,
        terms: &[(FactId, Q)],
        constant: Q,
        expect: Option<&Expr>,
    ) -> Result<FactId, String> {
        if kind == Kind::Eq && !constant.is_zero() || kind == Kind::Le && constant.is_positive() {
            return Err(invalid(format!("invalid {kind:?} linear constant")));
        }
        if kind == Kind::Int && !constant.is_integer() {
            return Err(invalid("invalid Int linear constant"));
        }
        let mut result_constant = constant.clone();
        let mut coefficients: BTreeMap<u32, Q> = BTreeMap::new();
        let mut emitted = Vec::new();
        for (fact_id, multiplier) in terms {
            self.visible(scope, *fact_id)?;
            check_q(multiplier)?;
            let fact = self.fact(*fact_id)?.clone();
            let allowed = fact.kind == Kind::Eq
                || (kind == Kind::Le && fact.kind == Kind::Le && multiplier.is_positive())
                || (kind == Kind::Int && fact.kind == Kind::Int && multiplier.is_integer());
            if !allowed {
                return Err(invalid(format!(
                    "invalid {kind:?} premise with multiplier {multiplier}"
                )));
            }
            result_constant += multiplier * &fact.expression.constant;
            check_q(&result_constant)?;
            for (index, coefficient) in &fact.expression.terms {
                *coefficients.entry(*index).or_insert_with(Q::zero) += multiplier * coefficient;
                check_q(coefficients.get(index).unwrap())?;
            }
            emitted.push((fact.reference, multiplier.clone()));
        }
        let expression = expr::canonical(result_constant, coefficients)?;
        if let Some(expected) = expect {
            if &expression != expected {
                return Err(invalid("linear residual mismatch"));
            }
        }
        self.register(
            scope,
            kind,
            expression,
            Step::Lin {
                id: 0,
                kind,
                constant,
                terms: emitted,
            },
        )
    }

    pub fn eq(
        &mut self,
        scope: ScopeId,
        terms: &[(FactId, Q)],
        constant: Q,
        expect: Option<&Expr>,
    ) -> Result<FactId, String> {
        self.lin(scope, Kind::Eq, terms, constant, expect)
    }

    pub fn le(
        &mut self,
        scope: ScopeId,
        terms: &[(FactId, Q)],
        constant: Q,
        expect: Option<&Expr>,
    ) -> Result<FactId, String> {
        self.lin(scope, Kind::Le, terms, constant, expect)
    }

    pub fn int(
        &mut self,
        scope: ScopeId,
        terms: &[(FactId, Q)],
        constant: Q,
        expect: Option<&Expr>,
    ) -> Result<FactId, String> {
        self.lin(scope, Kind::Int, terms, constant, expect)
    }

    pub fn box_le(&mut self, scope: ScopeId, expression: Expr) -> Result<FactId, String> {
        let model = self.scope(scope)?.model.clone();
        expression.validate(model.inner.vars.len())?;
        let mut residual = expression.constant.clone();
        let mut terms = Vec::new();
        for (index, coefficient) in &expression.terms {
            let variable = &model.inner.vars[*index as usize];
            let bound = if coefficient.is_positive() {
                &variable.upper
            } else {
                &variable.lower
            };
            let bound = bound
                .as_ref()
                .ok_or_else(|| invalid("box_le needs a finite declared bound"))?;
            residual += coefficient * bound;
            let fact = self.ref_fact(
                scope,
                if coefficient.is_positive() {
                    "VarUpper"
                } else {
                    "VarLower"
                },
                &Identifier::Index(*index),
            )?;
            terms.push((fact, coefficient.abs()));
        }
        if residual.is_positive() {
            return Err(invalid("declared bounds do not prove the supplied LE"));
        }
        self.le(scope, &terms, residual, Some(&expression))
    }

    pub fn eq_on_fixed(
        &mut self,
        scope: ScopeId,
        expression: Expr,
        fixes: &HashMap<u32, FactId>,
    ) -> Result<FactId, String> {
        let model = self.scope(scope)?.model.clone();
        expression.validate(model.inner.vars.len())?;
        let mut residual = expression.constant.clone();
        let mut terms = Vec::new();
        let mut bound_fixes = Vec::new();
        for (index, coefficient) in &expression.terms {
            if let Some(fact_id) = fixes.get(index) {
                self.visible(scope, *fact_id)?;
                let fact = self.fact(*fact_id)?.clone();
                if fact.kind != Kind::Eq
                    || fact.expression.terms.len() != 1
                    || fact.expression.terms[0].0 != *index
                {
                    return Err(invalid(
                        "eq_on_fixed needs a one-coordinate EQ for each explicit fixing",
                    ));
                }
                let multiplier = coefficient / &fact.expression.terms[0].1;
                residual -= &multiplier * &fact.expression.constant;
                terms.push((*fact_id, multiplier));
            } else {
                let variable = &model.inner.vars[*index as usize];
                let lower = variable
                    .lower
                    .as_ref()
                    .ok_or_else(|| invalid("eq_on_fixed needs a fixing for every coordinate"))?;
                if variable.upper.as_ref() != Some(lower) {
                    return Err(invalid("eq_on_fixed needs a fixing for every coordinate"));
                }
                residual += coefficient * lower;
                bound_fixes.push((*index, coefficient.clone()));
            }
        }
        if !residual.is_zero() {
            return Err(invalid(
                "fixed-coordinate equality has a nonzero exact residual",
            ));
        }
        let mut target = Expr::var(0);
        target.constant = Q::zero();
        for (index, coefficient) in bound_fixes {
            let x = model.var(&Identifier::Index(index))?;
            let equal = Expr {
                constant: -model.inner.vars[index as usize].lower.clone().unwrap(),
                terms: x.terms.clone(),
            };
            let fact = match self.find(scope, Kind::Eq, &equal)? {
                FindResult::Fact(fact) => fact,
                _ => {
                    let upper = self.ref_fact(scope, "VarUpper", &Identifier::Index(index))?;
                    let lower = self.ref_fact(scope, "VarLower", &Identifier::Index(index))?;
                    self.eqpair(scope, upper, lower)?
                }
            };
            terms.push((fact, coefficient));
        }
        self.eq(scope, &terms, Q::zero(), Some(&expression))
    }

    pub fn zero_sum(
        &mut self,
        scope: ScopeId,
        fact_id: FactId,
        zeros: &HashMap<u32, FactId>,
        scale: Q,
        coordinates: Option<&[u32]>,
    ) -> Result<HashMap<u32, FactId>, String> {
        self.visible(scope, fact_id)?;
        let fact = self.fact(fact_id)?.clone();
        if !matches!(fact.kind, Kind::Eq | Kind::Le)
            || scale.is_zero()
            || (fact.kind == Kind::Le && scale.is_negative())
        {
            return Err(invalid("zero_sum needs an EQ or a positively scaled LE"));
        }
        if !fact.expression.constant.is_zero() {
            return Err(invalid("zero_sum needs an exactly zero constant"));
        }
        let mut terms = vec![(fact_id, scale.clone())];
        let mut remaining: BTreeMap<u32, Q> = BTreeMap::new();
        for (index, coefficient) in &fact.expression.terms {
            let coefficient = coefficient * &scale;
            if let Some(equality) = zeros.get(index) {
                self.visible(scope, *equality)?;
                let zero = self.fact(*equality)?.clone();
                if zero.kind != Kind::Eq
                    || !zero.expression.constant.is_zero()
                    || zero.expression.terms.len() != 1
                    || zero.expression.terms[0].0 != *index
                {
                    return Err(invalid(
                        "zero_sum needs a one-coordinate zero EQ for each used fixing",
                    ));
                }
                terms.push((*equality, -coefficient / &zero.expression.terms[0].1));
            } else {
                remaining.insert(*index, coefficient);
            }
        }
        let selected: Vec<u32> = match coordinates {
            None => remaining.keys().copied().collect(),
            Some(items) => {
                let mut out = Vec::new();
                for item in items {
                    if !out.contains(item) {
                        out.push(*item);
                    }
                }
                out
            }
        };
        for index in &selected {
            if !remaining.contains_key(index) {
                return Err(invalid(
                    "zero_sum selected coordinate is not an unfixed term",
                ));
            }
        }
        if selected.is_empty() {
            return Ok(HashMap::new());
        }
        let single_eq = fact.kind == Kind::Eq && remaining.len() == 1;
        if !single_eq {
            for (index, coefficient) in &remaining {
                let lower = self.scope(scope)?.model.inner.vars[*index as usize]
                    .lower
                    .as_ref();
                if !coefficient.is_positive() || lower.is_none() || lower.unwrap().is_negative() {
                    return Err(invalid(
                        "zero_sum needs positive coefficients and declared nonnegative lower bounds",
                    ));
                }
            }
        }
        let remaining_expr = expr::canonical(Q::zero(), remaining.clone())?;
        let reduced = if terms.len() == 1 && scale.is_one() {
            fact_id
        } else {
            self.lin(scope, fact.kind, &terms, Q::zero(), Some(&remaining_expr))?
        };
        if single_eq {
            let index = selected[0];
            let coefficient = remaining[&index].clone();
            let x = self.scope(scope)?.model.var(&Identifier::Index(index))?;
            let fact = if coefficient.is_one() {
                reduced
            } else {
                self.eq(
                    scope,
                    &[(reduced, Q::one() / &coefficient)],
                    Q::zero(),
                    Some(&x),
                )?
            };
            return Ok(HashMap::from([(index, fact)]));
        }
        let mut nonnegative = HashMap::new();
        for index in remaining.keys() {
            let x = self.scope(scope)?.model.var(&Identifier::Index(*index))?;
            let lower = self.scope(scope)?.model.inner.vars[*index as usize]
                .lower
                .clone();
            let fact = if lower == Some(Q::zero()) {
                self.ref_fact(scope, "VarLower", &Identifier::Index(*index))?
            } else {
                self.box_le(scope, expr::neg(&x)?)?
            };
            nonnegative.insert(*index, fact);
        }
        let mut result = HashMap::new();
        for index in selected {
            let coefficient = remaining[&index].clone();
            let x = self.scope(scope)?.model.var(&Identifier::Index(index))?;
            let upper = if remaining.len() == 1 && coefficient.is_one() {
                reduced
            } else {
                let mut prem = vec![(reduced, Q::one() / &coefficient)];
                for (other, value) in &remaining {
                    if *other != index {
                        prem.push((nonnegative[other], value / &coefficient));
                    }
                }
                self.le(scope, &prem, Q::zero(), Some(&x))?
            };
            result.insert(index, self.eqpair(scope, upper, nonnegative[&index])?);
        }
        Ok(result)
    }

    pub fn round(&mut self, scope: ScopeId, le: FactId, integer: FactId) -> Result<FactId, String> {
        self.visible(scope, le)?;
        self.visible(scope, integer)?;
        let le_fact = self.fact(le)?.clone();
        let int_fact = self.fact(integer)?.clone();
        if le_fact.kind != Kind::Le
            || int_fact.kind != Kind::Int
            || le_fact.expression.terms != int_fact.expression.terms
        {
            return Err(invalid(
                "Round needs LE and INT facts with identical variable terms",
            ));
        }
        let difference = &le_fact.expression.constant - &int_fact.expression.constant;
        let ceiling = -(-difference.numer().clone()).div_floor(difference.denom());
        let expression = Expr {
            constant: int_fact.expression.constant.clone() + Q::from_integer(ceiling),
            terms: int_fact.expression.terms.clone(),
        };
        self.register(
            scope,
            Kind::Le,
            expression,
            Step::Round {
                id: 0,
                le: le_fact.reference,
                integer: int_fact.reference,
            },
        )
    }

    pub fn eqpair(
        &mut self,
        scope: ScopeId,
        positive: FactId,
        negative: FactId,
    ) -> Result<FactId, String> {
        self.visible(scope, positive)?;
        self.visible(scope, negative)?;
        let a = self.fact(positive)?.clone();
        let b = self.fact(negative)?.clone();
        if a.kind != Kind::Le || b.kind != Kind::Le || a.expression != expr::neg(&b.expression)? {
            return Err(invalid("EqPair needs opposite LE expressions"));
        }
        self.register(
            scope,
            Kind::Eq,
            a.expression,
            Step::EqPair {
                id: 0,
                positive: a.reference,
                negative: b.reference,
            },
        )
    }

    pub fn absurd(&self, scope: ScopeId, fact: FactId) -> Result<(), String> {
        self.visible(scope, fact)?;
        let data = self.fact(fact)?;
        if !data.expression.terms.is_empty() {
            return Err(invalid("Absurd requires a constant-only fact"));
        }
        let constant = &data.expression.constant;
        if (data.kind == Kind::Le && constant.is_positive())
            || (data.kind == Kind::Eq && !constant.is_zero())
        {
            Ok(())
        } else {
            Err(invalid(
                "Absurd requires positive constant LE or nonzero constant EQ",
            ))
        }
    }

    pub fn drop_facts(&mut self, scope: ScopeId, facts: &[FactId]) -> Result<(), String> {
        let mut ids = Vec::new();
        for fact in facts {
            self.visible(scope, *fact)?;
            match self.fact(*fact)?.reference {
                Ref::Local(id) => {
                    if ids.contains(&id) {
                        return Err(invalid("a Drop cannot list the same local fact twice"));
                    }
                    ids.push(id);
                }
                _ => return Err(invalid("only Local facts can be dropped")),
            }
        }
        for (fact, id) in facts.iter().zip(&ids) {
            self.scope_mut(scope)?.dropped.insert(*id);
            self.scope_mut(scope)?.facts.remove(id);
            let _ = fact;
        }
        self.scope_mut(scope)?.steps.push(Step::Drop { ids });
        self.scope_mut(scope)?.revision += 1;
        Ok(())
    }

    pub fn find(
        &mut self,
        scope: ScopeId,
        kind: Kind,
        expression: &Expr,
    ) -> Result<FindResult, String> {
        let model = self.scope(scope)?.model.clone();
        expression.validate(model.inner.vars.len())?;
        let trivial = match kind {
            Kind::Eq => expression.terms.is_empty() && expression.constant.is_zero(),
            Kind::Le => expression.terms.is_empty() && !expression.constant.is_positive(),
            Kind::Int => {
                expression.constant.is_integer()
                    && expression.terms.iter().all(|(index, coefficient)| {
                        coefficient.is_integer() && model.inner.vars[*index as usize].integer
                    })
            }
        };
        if trivial {
            return Ok(FindResult::Exact);
        }
        self.ensure_base(scope)?;
        let mut current = Some(scope);
        while let Some(id) = current {
            let mut local = self.scope(id)?.assumptions.clone();
            local.extend(self.scope(id)?.facts.values().copied());
            for fact in local.into_iter().rev() {
                let data = self.fact(fact)?;
                if (data.kind == kind || data.kind == Kind::Eq)
                    && data.expression == *expression
                    && self.visible(scope, fact).is_ok()
                {
                    return Ok(FindResult::Fact(fact));
                }
            }
            let base = self.scope(id)?.base_all.clone().unwrap_or_default();
            for fact in base.into_iter().rev() {
                let data = self.fact(fact)?;
                if (data.kind == kind || data.kind == Kind::Eq)
                    && data.expression == *expression
                    && self.visible(scope, fact).is_ok()
                {
                    return Ok(FindResult::Fact(fact));
                }
            }
            current = self.scope(id)?.parent;
        }
        Ok(FindResult::Missing)
    }

    pub fn branch(
        &mut self,
        scope: ScopeId,
        expression: Expr,
    ) -> Result<(ScopeId, FactId), String> {
        let parent = self.scope(scope)?.clone();
        let index = parent.assumptions.len() as u32;
        let child = self.new_scope(
            Arc::clone(&parent.model),
            Arc::clone(&parent.output_model),
            Some(scope),
            parent.assumptions.clone(),
        );
        {
            let item = self.scope_mut(child)?;
            item.layout = parent.layout.clone();
            item.layout_kind = parent.layout_kind;
            item.generated_variables = parent.generated_variables.clone();
            item.generated_rows = parent.generated_rows.clone();
        }
        let fact = self.push_fact(Kind::Le, expression, Ref::Assumption(index), child);
        self.scope_mut(child)?.assumptions.push(fact);
        Ok((child, fact))
    }

    pub fn split_options(
        &mut self,
        scope: ScopeId,
        expression: Expr,
        integer: Option<FactId>,
    ) -> Result<(Expr, Option<FactId>), String> {
        let model = self.scope(scope)?.model.clone();
        expression.validate(model.inner.vars.len())?;
        if let Some(fact) = integer {
            self.visible(scope, fact)?;
            let data = self.fact(fact)?;
            if data.kind != Kind::Int || data.expression != expression {
                return Err(invalid(
                    "integer split witness must prove INT of the exact split expression",
                ));
            }
        }
        Ok((expression, integer))
    }

    pub fn finish_split(
        &mut self,
        scope: ScopeId,
        expression: Expr,
        integer: Option<FactId>,
        left: ScopeId,
        right: ScopeId,
    ) -> Result<(), String> {
        let integer = integer
            .map(|fact| self.fact(fact).map(|f| f.reference.clone()))
            .transpose()?;
        self.scope_mut(scope)?.end = Some(ScopeEnd::Split {
            expression,
            integer,
            left,
            right,
        });
        self.scope_mut(scope)?.children = Some(vec![left, right]);
        self.scope_mut(scope)?.revision += 1;
        Ok(())
    }

    pub fn close_absurd(&mut self, scope: ScopeId, fact: FactId) -> Result<(), String> {
        self.absurd(scope, fact)?;
        let reference = self.fact(fact)?.reference.clone();
        self.scope_mut(scope)?.end = Some(ScopeEnd::Absurd { fact: reference });
        self.scope_mut(scope)?.revision += 1;
        Ok(())
    }

    pub fn set_return(
        &mut self,
        scope: ScopeId,
        map: Vec<Expr>,
        checks: Vec<Ref>,
    ) -> Result<(), String> {
        self.scope_mut(scope)?.end = Some(ScopeEnd::Return { map, checks });
        self.scope_mut(scope)?.children = None;
        self.scope_mut(scope)?.revision += 1;
        Ok(())
    }

    pub fn to_block(&self, scope: ScopeId) -> Result<Block, String> {
        let item = self.scope(scope)?;
        let end = match item
            .end
            .as_ref()
            .ok_or_else(|| invalid("proof scope has no terminal"))?
        {
            ScopeEnd::Return { map, checks } => End::Return {
                map: map.clone(),
                checks: checks.clone(),
            },
            ScopeEnd::Absurd { fact } => End::Absurd { fact: fact.clone() },
            ScopeEnd::Split {
                expression,
                integer,
                left,
                right,
            } => End::Split {
                expression: expression.clone(),
                integer: integer.clone(),
                left: Box::new(self.to_block(*left)?),
                right: Box::new(self.to_block(*right)?),
            },
            ScopeEnd::Interval { intervals, body } => End::IntervalLift {
                intervals: intervals.clone(),
                body: Box::new(self.to_block(*body)?),
            },
            ScopeEnd::Menu { menus, body } => End::MenuLift {
                menus: menus.clone(),
                body: Box::new(self.to_block(*body)?),
            },
            ScopeEnd::Signed {
                decompositions,
                body,
            } => End::SignedLift {
                decompositions: decompositions.clone(),
                body: Box::new(self.to_block(*body)?),
            },
            ScopeEnd::Flow { witness, body } => End::FlowLift {
                witness: witness.clone(),
                body: Box::new(self.to_block(*body)?),
            },
            ScopeEnd::Subflow { witness, body } => End::SubflowLift {
                witness: witness.clone(),
                body: Box::new(self.to_block(*body)?),
            },
        };
        Ok(Block {
            steps: item.steps.clone(),
            end,
        })
    }

    pub fn certificate(&self) -> Result<Certificate, String> {
        Ok(Certificate {
            forward: self.to_block(self.forward)?,
            reverse: self.to_block(self.reverse)?,
        })
    }

    pub fn standalone_certificate(&self) -> Result<Block, String> {
        self.to_block(self.forward)
    }

    pub fn revision(&self, scope: ScopeId) -> u64 {
        self.scopes[scope].revision
    }

    pub fn mapping(&self, scope: ScopeId) -> Option<Vec<Expr>> {
        self.scopes.get(scope).and_then(|item| {
            item.mapping
                .clone()
                .or_else(|| item.completion.as_ref().map(|c| c.mapping.clone()))
        })
    }

    pub fn completion_current(&self, scope: ScopeId) -> bool {
        let Some(request) = self.scopes[scope].completion.as_ref() else {
            return false;
        };
        let expected = self.scopes[scope].completed_revisions.as_ref();
        expected == Some(&self.ancestor_revisions(request.scope))
    }

    pub fn ancestor_revisions(&self, scope: ScopeId) -> Vec<(ScopeId, u64)> {
        let mut out = Vec::new();
        let mut current = Some(scope);
        while let Some(id) = current {
            out.push((id, self.scopes[id].revision));
            current = self.scopes[id].parent;
        }
        out
    }
}

fn with_step_id(step: Step, id: u32) -> Step {
    match step {
        Step::Lin {
            kind,
            constant,
            terms,
            ..
        } => Step::Lin {
            id,
            kind,
            constant,
            terms,
        },
        Step::Round { le, integer, .. } => Step::Round { id, le, integer },
        Step::Drop { ids } => Step::Drop { ids },
        Step::EqPair {
            positive, negative, ..
        } => Step::EqPair {
            id,
            positive,
            negative,
        },
        Step::Cases(mut case) => {
            case.id = id;
            Step::Cases(case)
        }
        Step::Plotkin {
            bits,
            distance,
            variables,
            cliques,
            ..
        } => Step::Plotkin {
            id,
            bits,
            distance,
            variables,
            cliques,
        },
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FindResult {
    Exact,
    Fact(FactId),
    Missing,
}

fn fact_tag(kind: &str) -> u8 {
    match kind {
        "VarLower" => 0,
        "VarUpper" => 1,
        "VarInt" => 2,
        "RowLower" => 3,
        "RowUpper" => 4,
        "RowEq" => 5,
        _ => 6,
    }
}

pub fn kind_name(kind: Kind) -> &'static str {
    match kind {
        Kind::Le => "Le",
        Kind::Eq => "Eq",
        Kind::Int => "Int",
    }
}

pub fn parse_kind(text: &str) -> Result<Kind, String> {
    match text {
        "Le" => Ok(Kind::Le),
        "Eq" => Ok(Kind::Eq),
        "Int" => Ok(Kind::Int),
        _ => Err(invalid("unknown fact kind")),
    }
}

#[derive(Clone, Debug)]
pub struct PivotEntry {
    pub pivot: u32,
    pub fact: FactId,
    pub divisor: Q,
}

#[derive(Clone, Debug)]
pub struct PivotPlan {
    pub entries: Vec<PivotEntry>,
    pub positions: HashMap<u32, Vec<usize>>,
}

impl PivotPlan {
    pub fn new(
        core: &ProofCore,
        scope: ScopeId,
        definitions: &[(u32, FactId)],
    ) -> Result<Self, String> {
        let mut entries = Vec::new();
        let mut positions: HashMap<u32, Vec<usize>> = HashMap::new();
        for (pivot, fact_id) in definitions {
            core.visible(scope, *fact_id)?;
            let fact = core.fact(*fact_id)?;
            if fact.kind != Kind::Eq {
                return Err(invalid(
                    "each rewrite definition must be an EQ with a nonzero selected pivot",
                ));
            }
            let divisor = fact
                .expression
                .terms
                .iter()
                .find(|(index, _)| index == pivot)
                .map(|(_, value)| value.clone())
                .ok_or_else(|| {
                    invalid("each rewrite definition must be an EQ with a nonzero selected pivot")
                })?;
            let position = entries.len();
            positions.entry(*pivot).or_default().push(position);
            entries.push(PivotEntry {
                pivot: *pivot,
                fact: *fact_id,
                divisor,
            });
        }
        Ok(Self { entries, positions })
    }

    pub fn reduce(
        &self,
        core: &ProofCore,
        expression: &Expr,
    ) -> Result<(Q, BTreeMap<u32, Q>, Vec<(FactId, Q)>), String> {
        let mut constant = expression.constant.clone();
        let mut coefficients: BTreeMap<u32, Q> = expression.terms.iter().cloned().collect();
        let mut active = Vec::new();
        let mut queued = HashSet::new();
        for index in coefficients.keys() {
            if let Some(positions) = self.positions.get(index) {
                for position in positions {
                    if queued.insert(*position) {
                        active.push(std::cmp::Reverse(*position));
                    }
                }
            }
        }
        let mut heap: BinaryHeap<std::cmp::Reverse<usize>> = active.into_iter().collect();
        let mut cancellation = Vec::new();
        while let Some(std::cmp::Reverse(position)) = heap.pop() {
            queued.remove(&position);
            let entry = &self.entries[position];
            let coefficient = coefficients
                .get(&entry.pivot)
                .cloned()
                .unwrap_or_else(Q::zero);
            if coefficient.is_zero() {
                continue;
            }
            let multiplier = -(&coefficient / &entry.divisor);
            let equation = &core.fact(entry.fact)?.expression;
            constant += &multiplier * &equation.constant;
            check_q(&constant)?;
            for (index, value) in &equation.terms {
                let updated =
                    coefficients.get(index).cloned().unwrap_or_else(Q::zero) + &multiplier * value;
                check_q(&updated)?;
                if updated.is_zero() {
                    coefficients.remove(index);
                } else {
                    coefficients.insert(*index, updated);
                    if let Some(order) = self.positions.get(index) {
                        for later in order.iter().filter(|later| **later > position) {
                            if queued.insert(*later) {
                                heap.push(std::cmp::Reverse(*later));
                            }
                        }
                    }
                }
            }
            cancellation.push((entry.fact, multiplier));
        }
        Ok((constant, coefficients, cancellation))
    }
}

impl ProofCore {
    pub fn rewrite(
        &mut self,
        scope: ScopeId,
        fact: FactId,
        definitions: &[(u32, FactId)],
        expect: Option<Expr>,
    ) -> Result<FactId, String> {
        self.visible(scope, fact)?;
        let plan = PivotPlan::new(self, scope, definitions)?;
        self.rewrite_plan(scope, fact, &plan, expect)
    }

    pub fn rewrite_plan(
        &mut self,
        scope: ScopeId,
        fact: FactId,
        plan: &PivotPlan,
        expect: Option<Expr>,
    ) -> Result<FactId, String> {
        self.visible(scope, fact)?;
        let data = self.fact(fact)?.clone();
        let (constant, coefficients, cancellation) = plan.reduce(self, &data.expression)?;
        let expected = match expect {
            Some(value) => value,
            None => expr::canonical(constant, coefficients)?,
        };
        let mut terms = vec![(fact, Q::one())];
        terms.extend(cancellation);
        self.lin(scope, data.kind, &terms, Q::zero(), Some(&expected))
    }

    pub fn derive_substitution(
        &mut self,
        scope: ScopeId,
        goal: Expr,
        definitions: &[(u32, FactId)],
        residual: FactId,
        kind: Option<Kind>,
    ) -> Result<FactId, String> {
        let plan = PivotPlan::new(self, scope, definitions)?;
        self.derive_substitution_plan(scope, goal, &plan, residual, kind)
    }

    pub fn derive_substitution_plan(
        &mut self,
        scope: ScopeId,
        goal: Expr,
        plan: &PivotPlan,
        residual: FactId,
        kind: Option<Kind>,
    ) -> Result<FactId, String> {
        self.visible(scope, residual)?;
        goal.validate(self.scope(scope)?.model.inner.vars.len())?;
        let data = self.fact(residual)?.clone();
        let kind = kind.unwrap_or(data.kind);
        let (constant, coefficients, cancellation) = plan.reduce(self, &goal)?;
        if constant != data.expression.constant
            || coefficients
                != data
                    .expression
                    .terms
                    .iter()
                    .cloned()
                    .collect::<BTreeMap<_, _>>()
        {
            return Err(invalid("substitution residual mismatch"));
        }
        let mut terms = vec![(residual, Q::one())];
        for (fact, multiplier) in cancellation {
            terms.push((fact, -multiplier));
        }
        self.lin(scope, kind, &terms, Q::zero(), Some(&goal))
    }

    pub fn substitution(
        &mut self,
        scope: ScopeId,
        definitions: &[(u32, FactId)],
        goals: &[Expr],
    ) -> Result<Vec<FactId>, String> {
        let plan = PivotPlan::new(self, scope, definitions)?;
        if plan.entries.is_empty() {
            return Ok(Vec::new());
        }
        let model = self.scope(scope)?.model.clone();
        let mut facts = Vec::new();
        for index in 0..model.inner.vars.len() as u32 {
            let variable = &model.inner.vars[index as usize];
            for (tag, present) in [
                ("VarLower", variable.lower.is_some()),
                ("VarUpper", variable.upper.is_some()),
                ("VarInt", variable.integer),
            ] {
                if present {
                    facts.push(self.ref_fact(scope, tag, &Identifier::Index(index))?);
                }
            }
        }
        for index in 0..model.inner.rows.len() as u32 {
            let row = &model.inner.rows[index as usize];
            let tags: Vec<&str> = if row.lower.is_some() && row.lower == row.upper {
                vec!["RowEq"]
            } else {
                let mut out = Vec::new();
                if row.lower.is_some() {
                    out.push("RowLower");
                }
                if row.upper.is_some() {
                    out.push("RowUpper");
                }
                out
            };
            for tag in tags {
                facts.push(self.ref_fact(scope, tag, &Identifier::Index(index))?);
            }
        }
        let mut generated = Vec::new();
        for fact in facts {
            let data = self.fact(fact)?.clone();
            if data
                .expression
                .terms
                .iter()
                .any(|(index, _)| plan.positions.contains_key(index))
            {
                generated.push(self.rewrite_plan(scope, fact, &plan, None)?);
            }
        }
        for goal in goals {
            goal.validate(model.inner.vars.len())?;
            if matches!(
                self.find(scope, Kind::Eq, goal)?,
                FindResult::Fact(_) | FindResult::Exact
            ) {
                continue;
            }
            let (constant, coefficients, cancellation) = plan.reduce(self, goal)?;
            if constant.is_zero() && coefficients.is_empty() {
                let terms = cancellation
                    .into_iter()
                    .map(|(fact, multiplier)| (fact, -multiplier))
                    .collect::<Vec<_>>();
                generated.push(self.eq(scope, &terms, Q::zero(), Some(goal))?);
            }
        }
        Ok(generated)
    }

    pub fn parity_fix(
        &mut self,
        scope: ScopeId,
        variable: u32,
        equality: FactId,
    ) -> Result<FactId, String> {
        self.visible(scope, equality)?;
        let model = self.scope(scope)?.model.clone();
        if !model.is_binary(&Identifier::Index(variable))? {
            return Err(invalid(
                "parity_fix requires an integer-mode binary coordinate in [0, 1]",
            ));
        }
        let data = self.fact(equality)?.clone();
        let expression = data.expression.clone();
        let selected = expression
            .terms
            .iter()
            .find(|(index, _)| *index == variable)
            .map(|(_, q)| q.clone())
            .unwrap_or_else(Q::zero);
        if data.kind != Kind::Eq
            || !expression.constant.is_integer()
            || !selected.is_integer()
            || selected.numer().is_even()
        {
            return Err(invalid(
                "parity_fix needs an EQ with integral constant and odd selected coefficient",
            ));
        }
        for (index, coefficient) in &expression.terms {
            if !model.inner.vars[*index as usize].integer {
                return Err(invalid(
                    "parity_fix requires declared integral coordinates in the equality",
                ));
            }
            if *index != variable && (!coefficient.is_integer() || coefficient.numer().is_odd()) {
                return Err(invalid(
                    "parity_fix requires every other coefficient to be an even integer",
                ));
            }
        }
        let parity = if (-expression.constant.numer()).is_odd() {
            1u32
        } else {
            0u32
        };
        let half = Q::new(1.into(), 2.into());
        let mut terms = vec![(equality, half.clone())];
        for (index, coefficient) in &expression.terms {
            if *index != variable {
                let int_fact = self.ref_fact(scope, "VarInt", &Identifier::Index(*index))?;
                terms.push((int_fact, -(coefficient * &half)));
            }
        }
        let adjustment = (Q::one() - &selected) * &half;
        if !adjustment.is_zero() {
            let int_fact = self.ref_fact(scope, "VarInt", &Identifier::Index(variable))?;
            terms.push((int_fact, adjustment));
        }
        let x = model.var(&Identifier::Index(variable))?;
        let constant =
            (Q::from_integer((-BigInt::from(parity)).into()) - &expression.constant) * &half;
        let expect = expr::scale(
            &expr::subtract(
                &x,
                &Expr {
                    constant: Q::from_integer(parity.into()),
                    terms: Vec::new(),
                },
            )?,
            &half,
        )?;
        let integral_half = self.int(scope, &terms, constant, Some(&expect))?;
        let variable_data = &model.inner.vars[variable as usize];
        let upper_bound = self.ref_fact(scope, "VarUpper", &Identifier::Index(variable))?;
        let upper_half = self.le(
            scope,
            &[(upper_bound, half.clone())],
            (variable_data.upper.as_ref().unwrap() - Q::one()) * &half,
            Some(&expr::scale(
                &expr::subtract(
                    &x,
                    &Expr {
                        constant: Q::one(),
                        terms: Vec::new(),
                    },
                )?,
                &half,
            )?),
        )?;
        let rounded_upper = self.round(scope, upper_half, integral_half)?;
        let upper = self.le(
            scope,
            &[(rounded_upper, Q::from_integer(2.into()))],
            Q::zero(),
            Some(&expr::subtract(
                &x,
                &Expr {
                    constant: Q::from_integer(parity.into()),
                    terms: Vec::new(),
                },
            )?),
        )?;
        let negative_half = self.int(
            scope,
            &[(integral_half, -Q::one())],
            Q::zero(),
            Some(&expr::scale(
                &expr::subtract(
                    &Expr {
                        constant: Q::from_integer(parity.into()),
                        terms: Vec::new(),
                    },
                    &x,
                )?,
                &half,
            )?),
        )?;
        let lower_bound = self.ref_fact(scope, "VarLower", &Identifier::Index(variable))?;
        let lower_half = self.le(
            scope,
            &[(lower_bound, half)],
            -(variable_data.lower.as_ref().unwrap() * &Q::new(1.into(), 2.into())),
            Some(&expr::scale(&expr::neg(&x)?, &Q::new(1.into(), 2.into()))?),
        )?;
        let rounded_lower = self.round(scope, lower_half, negative_half)?;
        let lower = self.le(
            scope,
            &[(rounded_lower, Q::from_integer(2.into()))],
            Q::zero(),
            Some(&expr::subtract(
                &Expr {
                    constant: Q::from_integer(parity.into()),
                    terms: Vec::new(),
                },
                &x,
            )?),
        )?;
        self.eqpair(scope, upper, lower)
    }

    pub fn plotkin(
        &mut self,
        scope: ScopeId,
        bits: u32,
        distance: u32,
        variables: &[(u32, u64)],
        cliques: &[FactId],
    ) -> Result<FactId, String> {
        if bits == 0 || bits > 64 || distance == 0 || distance > 64 || 2 * distance <= bits {
            return Err(invalid("invalid Plotkin parameters"));
        }
        let model = self.scope(scope)?.model.clone();
        let mut seen = HashSet::new();
        for (index, label) in variables {
            if !seen.insert(*index) {
                return Err(invalid("Plotkin variables must be distinct"));
            }
            if !model.is_binary(&Identifier::Index(*index))? {
                return Err(invalid("Plotkin requires actual binary variable domains"));
            }
            if bits < 64 && label >= &(1u64 << bits) {
                return Err(invalid("Plotkin label exceeds the selected bit width"));
            }
        }
        let mut membership: HashMap<u32, HashSet<usize>> = HashMap::new();
        for (index, _) in variables {
            membership.insert(*index, HashSet::new());
        }
        for (clique_index, fact_id) in cliques.iter().enumerate() {
            self.visible(scope, *fact_id)?;
            let fact = self.fact(*fact_id)?;
            if fact.kind != Kind::Le || fact.expression.constant != -Q::one() {
                return Err(invalid("Plotkin cliques require LE facts with constant -1"));
            }
            for (index, coefficient) in &fact.expression.terms {
                let lower = model.inner.vars[*index as usize].lower.as_ref();
                if coefficient != &Q::one() || lower.is_none() || lower.unwrap().is_negative() {
                    return Err(invalid(
                        "Plotkin clique coordinates require unit coefficients and nonnegative domains",
                    ));
                }
                if let Some(items) = membership.get_mut(index) {
                    items.insert(clique_index);
                }
            }
        }
        for (position, (index, label)) in variables.iter().enumerate() {
            for (other, other_label) in &variables[position + 1..] {
                if (label ^ other_label).count_ones() < distance
                    && membership.get(index).map_or(true, |left| {
                        membership
                            .get(other)
                            .map_or(true, |right| left.intersection(right).next().is_none())
                    })
                {
                    return Err(invalid("Plotkin close pair lacks a supplied clique"));
                }
            }
        }
        let bound = Q::new(
            BigInt::from(2 * distance),
            BigInt::from(2 * distance - bits),
        );
        let mut expression = Expr {
            constant: -bound,
            terms: variables
                .iter()
                .map(|(index, _)| (*index, Q::one()))
                .collect(),
        };
        expression.canonicalize()?;
        self.register(
            scope,
            Kind::Le,
            expression,
            Step::Plotkin {
                id: 0,
                bits,
                distance,
                variables: variables.to_vec(),
                cliques: cliques
                    .iter()
                    .map(|fact| self.fact(*fact).map(|f| f.reference.clone()))
                    .collect::<Result<Vec<_>, _>>()?,
            },
        )
    }
}

impl ProofCore {
    pub fn install_cases(
        &mut self,
        scope: ScopeId,
        kind: Kind,
        expression: Expr,
        split: Expr,
        integer: Option<FactId>,
        left: Derivation,
        right: Derivation,
    ) -> Result<FactId, String> {
        let integer = integer
            .map(|fact| self.fact(fact).map(|item| item.reference.clone()))
            .transpose()?;
        self.register(
            scope,
            kind,
            expression.clone(),
            Step::Cases(Box::new(CasesStep {
                id: 0,
                kind,
                expression,
                split,
                integer,
                left: Box::new(left),
                right: Box::new(right),
            })),
        )
    }
}

impl ProofCore {
    pub fn install_lift_extension(
        &mut self,
        parent: ScopeId,
        model: Model,
        extension: kernel_core::authoring::Extension,
    ) -> Result<ScopeId, String> {
        let parent_scope = self.scope(parent)?.clone();
        let generated_variables =
            (parent_scope.model.inner.vars.len() as u32..model.inner.vars.len() as u32).collect();
        let generated_rows =
            (parent_scope.model.inner.rows.len() as u32..model.inner.rows.len() as u32).collect();
        let child = self.new_scope(
            Arc::new(model),
            Arc::clone(&parent_scope.output_model),
            Some(parent),
            parent_scope.assumptions.clone(),
        );
        {
            let scope = self.scope_mut(child)?;
            scope.generated_variables = generated_variables;
            scope.generated_rows = generated_rows;
        }
        use kernel_core::authoring::Extension;
        let end = match extension {
            Extension::Interval(intervals) => {
                self.scope_mut(child)?.layout_kind = Some("Interval");
                ScopeEnd::Interval {
                    intervals,
                    body: child,
                }
            }
            Extension::Menu(menus) => {
                self.scope_mut(child)?.layout_kind = Some("Menu");
                ScopeEnd::Menu { menus, body: child }
            }
            Extension::Signed(decompositions) => {
                self.scope_mut(child)?.layout_kind = Some("Signed");
                ScopeEnd::Signed {
                    decompositions,
                    body: child,
                }
            }
            Extension::Flow(witness) => {
                self.scope_mut(child)?.layout_kind = Some("Flow");
                ScopeEnd::Flow {
                    witness,
                    body: child,
                }
            }
            Extension::Subflow(witness) => {
                self.scope_mut(child)?.layout_kind = Some("Subflow");
                ScopeEnd::Subflow {
                    witness,
                    body: child,
                }
            }
        };
        self.scope_mut(parent)?.end = Some(end);
        self.scope_mut(parent)?.children = Some(vec![child]);
        self.scope_mut(parent)?.revision += 1;
        Ok(child)
    }
}
