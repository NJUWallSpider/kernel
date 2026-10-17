//! Native Return planning and witness completion over the kernel obligation walker.
use crate::proof::{AssignmentValue, CompletionRequest, ProofCore, ScopeId, Selector, kind_name};
use kernel_core::compiler::{
    self, Assignment, AssignmentFact, AuthoringFact, ResolveResult, ResolveReturn, ReturnPlan,
};
use kernel_core::model::Expr;
use kernel_core::proof::{Kind, Ref};
use kernel_core::verify::{Limits, ObligationOrigin, ReturnObligation};

#[derive(Clone, Debug)]
pub struct Obligation {
    pub index: usize,
    pub kind: Kind,
    pub expression: Expr,
    pub origin: ObligationOrigin,
}

impl ProofCore {
    pub fn plan(
        &self,
        scope: ScopeId,
        mapping: &[Expr],
        limits: &Limits,
    ) -> Result<Vec<Obligation>, String> {
        let item = self.scope(scope)?;
        let plan = ReturnPlan {
            map: mapping.to_vec(),
        };
        let values =
            compiler::plan_return(&item.model.inner, &item.output_model.inner, &plan, limits)?;
        Ok(values
            .into_iter()
            .enumerate()
            .map(|(index, value)| Obligation {
                index,
                kind: value.kind,
                expression: value.expression,
                origin: value.origin,
            })
            .collect())
    }

    pub fn resolve(
        &self,
        scope: ScopeId,
        mapping: &[Expr],
        witnesses: &[(Selector, AssignmentValue)],
        auto: bool,
        limits: &Limits,
    ) -> Result<ResolveResult, String> {
        let item = self.scope(scope)?;
        let mut facts = Vec::new();
        let mut assignments = Vec::new();
        for fact_id in item.facts.values().copied() {
            if self.visible(scope, fact_id).is_err() {
                continue;
            }
            facts.push(authoring_fact(self, fact_id)?);
        }
        for fact_id in &item.assumptions {
            facts.push(authoring_fact(self, *fact_id)?);
        }
        for (selector, value) in item
            .assigned
            .iter()
            .map(|(s, v)| (s.clone(), v.clone()))
            .chain(witnesses.iter().cloned())
        {
            let (index, label) = match selector {
                Selector::Index(index) => (Some(index), None),
                Selector::Label(label) => (None, Some(label)),
            };
            let fact = match value {
                AssignmentValue::Exact => AssignmentFact::Exact,
                AssignmentValue::Fact(fact) => AssignmentFact::Fact(authoring_fact(self, fact)?),
            };
            assignments.push(Assignment { index, label, fact });
        }
        let spec = ResolveReturn {
            plan: ReturnPlan {
                map: mapping.to_vec(),
            },
            facts,
            assignments,
            auto,
        };
        compiler::resolve_return(&item.model.inner, &item.output_model.inner, spec, limits)
    }

    pub fn complete(
        &mut self,
        scope: ScopeId,
        mapping: &[Expr],
        witnesses: &[(Selector, AssignmentValue)],
        auto: bool,
        limits: &Limits,
    ) -> Result<(), String> {
        let result = self.resolve(scope, mapping, witnesses, auto, limits)?;
        if !result.missing.is_empty() {
            let details = result
                .missing
                .iter()
                .take(8)
                .map(|item| {
                    format!(
                        "{}: {} {:?}",
                        obligation_label(&item.obligation),
                        kind_name(item.obligation.kind),
                        item.obligation.expression
                    )
                })
                .collect::<Vec<_>>()
                .join("; ");
            return Err(format!(
                "INVALID {} undischarged obligations; {details}",
                result.missing.len()
            ));
        }
        let checks: Vec<Ref> = result
            .checks
            .into_iter()
            .map(|item| item.ok_or_else(|| "INVALID missing Return witness".to_string()))
            .collect::<Result<_, _>>()?;
        self.set_return(scope, mapping.to_vec(), checks)?;
        if self.revision(scope) == 0 {
            self.scope_mut(scope)?.revision = 1;
        }
        self.scope_mut(scope)?.mapping = None;
        self.scope_mut(scope)?.completion = Some(CompletionRequest {
            scope,
            mapping: mapping.to_vec(),
            witnesses: witnesses.to_vec(),
            auto,
        });
        self.scope_mut(scope)?.completed_revisions = Some(self.ancestor_revisions(scope));
        Ok(())
    }

    pub fn refresh_completions(&mut self, limits: &Limits) -> Result<(), String> {
        let ids: Vec<ScopeId> = (0..self.scopes.len())
            .filter(|id| self.scopes[*id].completion.is_some())
            .collect();
        for id in ids {
            if self.completion_current(id) {
                continue;
            }
            let request = self
                .scopes
                .get(id)
                .and_then(|scope| scope.completion.clone())
                .ok_or_else(|| "INVALID missing completion request".to_string())?;
            self.complete(
                request.scope,
                &request.mapping,
                &request.witnesses,
                request.auto,
                limits,
            )?;
        }
        Ok(())
    }
}

fn authoring_fact(core: &ProofCore, fact: usize) -> Result<AuthoringFact, String> {
    let data = core.fact(fact)?;
    Ok(AuthoringFact {
        kind: data.kind,
        expression: data.expression.clone(),
        reference: data.reference.clone(),
    })
}

fn obligation_label(obligation: &ReturnObligation) -> String {
    let mut label = obligation.origin.kind.clone();
    if let Some(name) = &obligation.origin.name {
        label.push('[');
        label.push_str(name);
        label.push(']');
    } else if let Some(index) = obligation.origin.index {
        label.push_str(&format!("[{index}]"));
    }
    label
}
