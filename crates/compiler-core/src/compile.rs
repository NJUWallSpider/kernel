//! Lower once to an immutable certificate; encode RPA and RPX independently.
use crate::error::Error;
use crate::proof::ProofCore;
use kernel_core::proof::{Block, Certificate, End, Step};
use kernel_core::verify::{self, Limits, Statistics};

#[derive(Clone, Debug)]
pub struct CompiledProof {
    pub certificate: Certificate,
    pub rpa: String,
    pub rpx: Vec<u8>,
    pub source: Vec<u8>,
    pub target: Vec<u8>,
    pub summary: serde_json::Value,
}

impl ProofCore {
    pub fn compile(&mut self) -> Result<std::sync::Arc<CompiledProof>, Error> {
        if let Some(compiled) = &self.compiled {
            return Ok(compiled.clone());
        }
        let certificate = self.certificate()?;
        let rpa = kernel_core::rpa::disassemble(&certificate)?;
        let rpx = kernel_core::codec::encode_certificate(&certificate)?;
        let mut counts = Counts::default();
        counts.block(&certificate.forward);
        counts.block(&certificate.reverse);
        let summary = serde_json::json!({"steps":counts.steps,"checks":counts.checks,"maps":counts.maps,"linear_premises":counts.linear_premises,"directions":2,"rpa_bytes":rpa.len(),"rpx_bytes":rpx.len()});
        let compiled = std::sync::Arc::new(CompiledProof {
            source: self.source.to_mcm()?,
            target: self.target.to_mcm()?,
            certificate,
            rpa,
            rpx,
            summary,
        });
        self.lowering_count += 1;
        self.compiled = Some(compiled.clone());
        Ok(compiled)
    }

    pub fn verify(&mut self, limits: &Limits) -> Result<Statistics, Error> {
        let compiled = self.compile()?;
        verify::verify(
            &self.source.inner,
            &self.target.inner,
            &compiled.certificate,
            limits,
        )
        .map_err(Error::from)
    }

    pub fn preflight(&mut self) -> Result<serde_json::Value, Error> {
        let compiled = self.compile()?;
        Ok(compiled.summary.clone())
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
