//! The only compiler proof path: certificate -> RPA 12 -> certificate -> RPX.
use crate::proof::ProofCore;
use kernel_core::proof::{Block, Certificate, End, Step};
use kernel_core::verify::{self, Limits, Statistics};

#[derive(Clone, Debug)]
pub struct CompiledProof {
    pub certificate: Certificate,
    pub rpa: String,
    pub rpx: Vec<u8>,
}

impl ProofCore {
    pub fn compile(&mut self, limits: &Limits) -> Result<CompiledProof, String> {
        self.refresh_completions(limits)?;
        let original = self.certificate()?;
        let rpa = kernel_core::rpa::disassemble(&original)?;
        drop(original);
        let certificate = kernel_core::rpa::assemble(&rpa)?;
        let rpx = kernel_core::codec::encode_certificate(&certificate)?;
        Ok(CompiledProof {
            certificate,
            rpa,
            rpx,
        })
    }

    pub fn verify(&mut self, limits: &Limits) -> Result<Statistics, String> {
        let compiled = self.compile(limits)?;
        verify::verify(
            &self.source.inner,
            &self.target.inner,
            &compiled.certificate,
            limits,
        )
    }

    pub fn preflight(&mut self, limits: &Limits) -> Result<serde_json::Value, String> {
        let compiled = self.compile(limits)?;
        let mut counts = Counts::default();
        counts.block(&compiled.certificate.forward);
        counts.block(&compiled.certificate.reverse);
        Ok(serde_json::json!({
            "steps": counts.steps,
            "checks": counts.checks,
            "maps": counts.maps,
            "linear_premises": counts.linear_premises,
            "directions": 2,
            "rpa_bytes": compiled.rpa.len(),
            "rpx_bytes": compiled.rpx.len(),
        }))
    }
}

#[derive(Default)]
struct Counts {
    steps: u64,
    checks: u64,
    maps: u64,
    linear_premises: u64,
}

impl Counts {
    fn block(&mut self, block: &Block) {
        self.steps += block.steps.len() as u64;
        for step in &block.steps {
            if let Step::Lin { terms, .. } = step {
                self.linear_premises += terms.len() as u64;
            }
            if let Step::Cases(case) = step {
                self.derivation(&case.left);
                self.derivation(&case.right);
            }
        }
        match &block.end {
            End::Return { map, checks } => {
                self.maps += map.len() as u64;
                self.checks += checks.len() as u64;
            }
            End::Split { left, right, .. } => {
                self.block(left);
                self.block(right);
            }
            End::IntervalLift { intervals, body } => {
                for interval in intervals {
                    self.checks += interval.checks.len() as u64;
                }
                self.block(body);
            }
            End::MenuLift { menus, body } => {
                for menu in menus {
                    self.checks += menu.checks.len() as u64;
                }
                self.block(body);
            }
            End::SignedLift {
                decompositions,
                body,
            } => {
                for item in decompositions {
                    self.checks += item.checks.len() as u64;
                }
                self.block(body);
            }
            End::FlowLift { witness, body } => {
                for group in &witness.groups {
                    self.checks += (group.nonnegative.len() + group.balances.len()) as u64;
                }
                self.block(body);
            }
            End::SubflowLift { witness, body } => {
                for group in &witness.groups {
                    self.checks += (group.nonnegative.len() + group.balances.len()) as u64;
                }
                self.block(body);
            }
            End::Absurd { .. } => {}
        }
    }

    fn derivation(&mut self, derivation: &kernel_core::proof::Derivation) {
        self.steps += derivation.steps.len() as u64;
        for step in &derivation.steps {
            if let Step::Lin { terms, .. } = step {
                self.linear_premises += terms.len() as u64;
            }
            if let Step::Cases(case) = step {
                self.derivation(&case.left);
                self.derivation(&case.right);
            }
        }
        self.checks += 1;
    }
}
