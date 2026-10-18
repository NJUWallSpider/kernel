//! One native obligation store and deterministic exact witness resolution.
use crate::{
    error::Error,
    model::Identifier,
    proof::{FactId, FindResult, ProofCore, ScopeId, ScopeState},
    space::{BoundExpr, pretty},
};
use kernel_core::{
    compiler::{ReturnPlan, visit_return},
    model::Expr,
    proof::{Kind, Ref},
    verify::{Limits, ObligationOrigin},
};
use std::{collections::HashMap, sync::Arc};

#[derive(Clone, Debug)]
pub struct Obligation {
    pub index: usize,
    pub kind: Kind,
    pub expression: Expr,
    pub origin: ObligationOrigin,
    pub label: String,
}
#[derive(Clone, Debug)]
pub struct MappingSpec {
    pub same_name: bool,
    pub overrides: HashMap<u32, Expr>,
}

impl ProofCore {
    pub fn ensure_open(&self, scope: ScopeId) -> Result<(), Error> {
        if self.scope(scope)?.state != ScopeState::Open {
            return Err(Error::Scope(
                "scope is sealed or has an active branch/extension".into(),
            ));
        }
        Ok(())
    }
    pub fn set_mapping(
        &mut self,
        scope: ScopeId,
        same_name: bool,
        values: Vec<(String, BoundExpr)>,
    ) -> Result<(), Error> {
        self.ensure_open(scope)?;
        let item = self.scope(scope)?;
        let mut overrides = HashMap::new();
        for (name, value) in values {
            let index = item
                .output_model
                .index(&Identifier::Name(name), false)
                .map_err(|e| Error::Mapping(e.to_string()))?;
            value.in_space(&item.model.space)?;
            value.value.validate(item.model.inner.vars.len())?;
            if overrides.insert(index, (*value.value).clone()).is_some() {
                return Err(Error::Mapping("duplicate output coordinate".into()));
            }
        }
        let spec = MappingSpec {
            same_name,
            overrides,
        };
        let mut expanded = Vec::with_capacity(item.output_model.inner.vars.len());
        for (index, variable) in item.output_model.inner.vars.iter().enumerate() {
            let value = spec
                .overrides
                .get(&(index as u32))
                .cloned()
                .or_else(|| {
                    if same_name {
                        item.model
                            .var_index
                            .get(&variable.name)
                            .map(|i| Expr::var(*i))
                    } else {
                        None
                    }
                })
                .ok_or_else(|| {
                    Error::Mapping(format!("missing output coordinate {:?}", variable.name))
                })?;
            expanded.push(value);
        }
        let item = self.scope_mut(scope)?;
        item.mapping_spec = Some(spec);
        item.mapping = Some(Arc::new(expanded));
        item.map_epoch += 1;
        item.goals = None;
        item.assigned.clear();
        Ok(())
    }
    pub fn obligations(&mut self, scope: ScopeId) -> Result<Arc<Vec<Obligation>>, Error> {
        if let Some(goals) = &self.scope(scope)?.goals {
            return Ok(goals.clone());
        }
        let item = self.scope(scope)?;
        let mapping = item.mapping.as_ref().ok_or_else(|| {
            Error::Mapping("declare an output map before requesting goals".into())
        })?;
        let mut goals = Vec::new();
        visit_return(
            &item.model.inner,
            &item.output_model.inner,
            &ReturnPlan {
                map: mapping.as_ref().clone(),
            },
            &Limits::default(),
            |o| {
                let label = match (&o.origin.name, o.origin.index) {
                    (Some(name), _) => format!("{}[{name}]", o.origin.kind),
                    (_, Some(i)) => format!("{}[{i}]", o.origin.kind),
                    _ => o.origin.kind.clone(),
                };
                goals.push(Obligation {
                    index: goals.len(),
                    kind: o.kind,
                    expression: o.expression,
                    origin: o.origin,
                    label,
                });
                Ok(())
            },
        )?;
        let goals = Arc::new(goals);
        self.scope_mut(scope)?.goals = Some(goals.clone());
        Ok(goals)
    }
    pub fn resolve_goal(
        &mut self,
        scope: ScopeId,
        goal: &Obligation,
    ) -> Result<Option<Ref>, Error> {
        if let Some(id) = self.scope(scope)?.assigned.get(&goal.index).copied() {
            self.visible(scope, id)
                .map_err(|e| Error::Scope(e.to_string()))?;
            let f = self.fact(id)?;
            if f.expression != goal.expression || (f.kind != goal.kind && f.kind != Kind::Eq) {
                return Err(Error::Derivation(format!(
                    "witness does not prove {}",
                    goal.label
                )));
            }
            return Ok(Some(f.reference.clone()));
        }
        Ok(match self.find(scope, goal.kind, &goal.expression)? {
            FindResult::Exact => Some(Ref::Exact),
            FindResult::Fact(id) => Some(self.fact(id)?.reference.clone()),
            FindResult::Missing => None,
        })
    }
    pub fn finish(&mut self, scope: ScopeId) -> Result<(), Error> {
        if self.scope(scope)?.state == ScopeState::Sealed {
            return Ok(());
        }
        self.ensure_open(scope)?;
        if self.scope(scope)?.derivation {
            return Err(Error::Scope("use conclude() for a Cases derivation".into()));
        }
        let goals = self.obligations(scope)?;
        let mut checks = Vec::with_capacity(goals.len());
        let mut missing = Vec::new();
        for goal in goals.iter() {
            match self.resolve_goal(scope, goal)? {
                Some(r) => checks.push(r),
                None => missing.push(goal),
            }
        }
        if !missing.is_empty() {
            let space = &self.scope(scope)?.model.space;
            let mut message = format!("{} unresolved obligations", missing.len());
            for goal in missing.iter().take(20) {
                message.push_str(&format!(
                    "\n  {}: {} {}",
                    goal.label,
                    pretty(&goal.expression, Some(space)),
                    match goal.kind {
                        Kind::Le => "<= 0",
                        Kind::Eq => "= 0",
                        Kind::Int => "is integer",
                    }
                ));
            }
            return Err(Error::Unproved(message));
        }
        let map = self.scope(scope)?.mapping.clone().unwrap();
        self.set_return(scope, map, checks)?;
        Ok(())
    }
    pub fn assign_goal(&mut self, scope: ScopeId, index: usize, fact: FactId) -> Result<(), Error> {
        self.ensure_open(scope)?;
        self.visible(scope, fact)
            .map_err(|e| Error::Scope(e.to_string()))?;
        let goals = self.obligations(scope)?;
        let goal = goals
            .get(index)
            .ok_or_else(|| Error::Unproved("unknown goal".into()))?;
        let data = self.fact(fact)?;
        if data.expression != goal.expression || (data.kind != goal.kind && data.kind != Kind::Eq) {
            return Err(Error::Derivation(format!(
                "witness does not prove {}",
                goal.label
            )));
        }
        self.scope_mut(scope)?.assigned.insert(index, fact);
        Ok(())
    }
    pub fn transaction<T>(
        &mut self,
        scope: ScopeId,
        run: impl FnOnce(&mut Self) -> Result<T, Error>,
    ) -> Result<T, Error> {
        self.ensure_open(scope)?;
        let facts = self.facts.len();
        let steps = self.scope(scope)?.steps.len();
        let next = self.next_local;
        match run(self) {
            Ok(value) => Ok(value),
            Err(error) => {
                self.facts.truncate(facts);
                self.next_local = next;
                let item = self.scope_mut(scope)?;
                item.steps.truncate(steps);
                item.facts.retain(|_, id| *id < facts);
                item.base.retain(|_, id| *id < facts);
                item.base_indexed = false;
                item.fact_index.clear();
                item.indexed_facts = 0;
                Err(match error {
                    Error::Invalid(message) => Error::Derivation(message),
                    other => other,
                })
            }
        }
    }
}

impl ProofCore {
    /// Check an explicitly supplied reference without searching the fact arena.
    pub fn check_witness(
        &mut self,
        scope: ScopeId,
        reference: &Ref,
        kind: Kind,
        expression: &Expr,
    ) -> Result<bool, Error> {
        if *reference == Ref::Exact {
            return Ok(matches!(
                self.find(scope, kind, expression)?,
                FindResult::Exact
            ));
        }
        let id = match reference {
            Ref::VarLower(i) => self.ref_fact(scope, "VarLower", &Identifier::Index(*i))?,
            Ref::VarUpper(i) => self.ref_fact(scope, "VarUpper", &Identifier::Index(*i))?,
            Ref::VarInt(i) => self.ref_fact(scope, "VarInt", &Identifier::Index(*i))?,
            Ref::RowLower(i) => self.ref_fact(scope, "RowLower", &Identifier::Index(*i))?,
            Ref::RowUpper(i) => self.ref_fact(scope, "RowUpper", &Identifier::Index(*i))?,
            Ref::RowEq(i) => self.ref_fact(scope, "RowEq", &Identifier::Index(*i))?,
            Ref::Assumption(i) => *self
                .scope(scope)?
                .assumptions
                .get(*i as usize)
                .ok_or_else(|| Error::Scope("missing assumption".into()))?,
            Ref::Local(local) => {
                let mut current = Some(scope);
                let mut found = None;
                while let Some(s) = current {
                    if let Some(f) = self.scope(s)?.facts.get(local) {
                        found = Some(*f);
                        break;
                    }
                    current = self.scope(s)?.parent;
                }
                found.ok_or_else(|| Error::Scope("local fact is not visible".into()))?
            }
            Ref::Exact => unreachable!(),
        };
        self.visible(scope, id)
            .map_err(|e| Error::Scope(e.to_string()))?;
        let fact = self.fact(id)?;
        Ok((fact.kind == kind || fact.kind == Kind::Eq) && fact.expression == *expression)
    }
}
