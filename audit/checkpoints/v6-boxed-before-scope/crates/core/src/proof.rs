//! Versioned proof data. Every direction is an independently requested total map.
use crate::model::{Expr, Q};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Claim {
    pub reverse: bool,
    pub input_integers: bool,
    pub output_integers: bool,
    pub objective: Objective,
    /// (input coordinate, output coordinate) whose values must be preserved.
    pub projection: Vec<(u32, u32)>,
    /// V5: exact affine observations in original input/output coordinates.
    #[serde(default,skip_serializing_if="Vec::is_empty")]
    pub affine_projection:Vec<(Expr,Expr)>,
    /// Optional opposing affine claim whose composed map must be the input identity.
    #[serde(default)]
    pub inverse: Option<u32>,
    /// V3: a global lower bound on this direction's input objective.
    #[serde(default,with="crate::rpa::option_scalar",skip_serializing_if="Option::is_none")]
    pub input_objective_lower: Option<Q>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Objective { None, Equal, NonIncreasing }
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Certificate { pub claims: Vec<Claim>, pub blocks: Vec<Block>, #[serde(default,skip_serializing_if="Vec::is_empty")] pub points:Vec<PointWitness> }
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {pub claims:Vec<Claim>,#[serde(default)]pub points:Vec<PointClaim>}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub enum PointClaim {
    Feasible {target:bool,integers:bool,#[serde(default,with="crate::rpa::option_scalar")]objective:Option<Q>},
    Strictness {inclusion_claim:u32},
    /// V6: strict inclusion of the coordinate/affine observation images.
    FiberStrictness {inclusion_claim:u32},
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PointWitness {pub claim:PointClaim,#[serde(with="crate::rpa::scalar_vec")]pub values:Vec<Q>,#[serde(default,skip_serializing_if="Option::is_none")]pub refutation:Option<Block>}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Block { pub steps: Vec<Step>, pub end: End }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Kind { Le, Eq, Int }
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Ref {
    VarLower(u32), VarUpper(u32), VarInt(u32),
    RowLower(u32), RowUpper(u32), RowEq(u32),
    Local(u32), Assumption(u32), Exact,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub enum Step {
    /// Constant + sum multiplier*fact. Rules depend on the resulting kind.
    Lin { id: u32, kind: Kind, #[serde(with="crate::rpa::scalar")] constant: Q, #[serde(with="crate::rpa::ref_terms")] terms: Vec<(Ref, Q)> },
    /// Integer-valued expression and LE expression must differ only by a constant.
    Round { id: u32, le: Ref, integer: Ref },
    Drop { ids: Vec<u32> },
    /// V2: exact antisymmetry; output EQ has the positive LE's expression.
    EqPair { id: u32, positive: Ref, negative: Ref },
    /// V2: local exhaustive cases exporting one common parent proposition.
    Cases(Box<CasesStep>),
    /// V3 trusted Plotkin bound from checked binary domains and close-pair cliques.
    Plotkin {id:u32,bits:u32,distance:u32,variables:Vec<(u32,u64)>,cliques:Vec<Ref>},
}
/// Rare large payload is indirect so ordinary proof steps keep compact slots.
/// The external Cases JSON object and RPX fields remain unchanged.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CasesStep {
    pub id:u32,pub kind:Kind,pub expression:Expr,pub split:Expr,
    pub integer:Option<Ref>,pub left:Box<Derivation>,pub right:Box<Derivation>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Derivation { pub steps: Vec<Step>, pub end: DerivationEnd }
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum DerivationEnd { Witness(Ref), Absurd(Ref) }
/// V5 independent real interval choices; all expressions use the parent scope.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct IntervalWitness{pub lower:Vec<Expr>,pub upper:Vec<Expr>,pub checks:Vec<Ref>}
/// V4 graph and simultaneous common-source flow extension witness.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FlowWitness{pub nodes:u32,pub arcs:Vec<(u32,u32)>,pub groups:Vec<FlowGroup>}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FlowGroup{
    pub source:u32,
    #[serde(with="crate::rpa::expr_terms")]
    pub commodities:Vec<(u32,Q)>,
    pub flows:Vec<Expr>,
    pub nonnegative:Vec<Ref>,
    pub balances:Vec<Ref>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub enum End {
    /// V5: jointly append independent interval choices after all pair premises.
    IntervalLift{intervals:Vec<IntervalWitness>,body:Box<Block>},
    /// V4: jointly extend the input by real commodity flows, after all premises.
    FlowLift{witness:FlowWitness,body:Box<Block>},
    /// One common output vector; one reference for EVERY kernel-derived obligation.
    Return { map: Vec<Expr>, checks: Vec<Ref> },
    /// e<=0 and -e<=0, or e<=0 and 1-e<=0 when `integer` proves INT(e).
    Split { expression: Expr, integer: Option<Ref>, left: Box<Block>, right: Box<Block> },
    /// A checked constant-positive LE or nonzero-constant EQ closes an empty domain.
    Absurd { fact: Ref },
}
