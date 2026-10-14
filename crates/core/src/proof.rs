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
    /// V9: restrict this direction's actual input domain to this objective level.
    /// This alone asserts neither optimality nor nonemptiness.
    #[serde(default,with="crate::rpa::option_scalar",skip_serializing_if="Option::is_none")]
    pub input_objective_level: Option<Q>,
    /// V10: restrict the original input coordinates to this affine expression <= 0.
    /// No feasibility, optimality or whole-model inclusion follows by itself.
    #[serde(default,skip_serializing_if="Option::is_none")]
    pub input_halfspace: Option<Expr>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Objective { None, Equal, NonIncreasing }
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
#[derive(Default)]
pub struct Certificate { #[serde(default,skip_serializing_if="Vec::is_empty")] pub improvements:Vec<ImprovementWitness>, #[serde(default,skip_serializing_if="Vec::is_empty")] pub bijections:Vec<BijectionWitness>, pub claims: Vec<Claim>, pub blocks: Vec<Block>, #[serde(default,skip_serializing_if="Vec::is_empty")] pub points:Vec<PointWitness> }
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
#[derive(Default)]
pub struct Request {#[serde(default)]pub improvements:Vec<ImprovementClaim>,#[serde(default)]pub bijections:Vec<BijectionClaim>,pub claims:Vec<Claim>,#[serde(default)]pub points:Vec<PointClaim>}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub enum PointClaim {
    /// V10: a full LP point is feasible on one side, but its complete
    /// caller-specified affine image is infeasible in the other actual LP.
    /// No global containment assertion follows.
    ImageExclusion {point_in_target:bool,map:Vec<Expr>},
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
/// V10: jointly retain the demanded part of a nonnegative real flow.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SubflowWitness{pub nodes:u32,pub arcs:Vec<(u32,u32)>,pub groups:Vec<SubflowGroup>}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SubflowGroup{
    pub source:u32,
    #[serde(with="crate::rpa::expr_terms")]
    pub demands:Vec<(u32,Q)>,
    pub flows:Vec<Expr>,pub nonnegative:Vec<Ref>,pub balances:Vec<Ref>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub enum End {
    /// V10: simultaneous demand-bounded subflows, with old-scope premises.
    SubflowLift{witness:SubflowWitness,body:Box<Block>},
    /// V10: complete same-model improving tuple on a strict domain.
    ImproveReturn {map:Vec<Expr>,checks:Vec<Ref>,margin:ImprovementMargin},
    /// V10: contradict the root's strictly positive requested expression.
    PositiveRefutation {fact:Ref},
    /// V8: jointly split bounded signed real expressions into activated directions.
    SignedLift{decompositions:Vec<SignedWitness>,body:Box<Block>},
    /// V7: jointly append optional binary menus after six old-scope premises each.
    MenuLift{menus:Vec<MenuWitness>,body:Box<Block>},
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

/// V10. For every feasible x with positive(x)>0 there exists one feasible
/// y in the SAME complete actual model with f(y)<f(x). No optimum is assumed.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ImprovementClaim {pub target:bool,pub integers:bool,pub positive:Expr}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ImprovementWitness {pub claim:ImprovementClaim,pub block:Block}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ImprovementMargin {
    Constant(#[serde(with="crate::rpa::scalar")] Q),
    Predicate(#[serde(with="crate::rpa::scalar")] Q),
}

/// V7: exact caller-bound pair of opposing directional claims.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BijectionClaim {pub forward_claim:u32,pub reverse_claim:u32}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BijectionWitness {pub claim:BijectionClaim,pub injectivity:EqualityProof}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EqualityProof {pub steps:Vec<Step>,pub checks:Vec<Ref>}
/// V7: a bounded optional menu represented by an integer activation and index.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MenuWitness {pub maximum_index:u32,pub activation:Expr,pub index:Expr,pub checks:Vec<Ref>}

/// V8 old-scope binary activation, real flow, nonnegative exact capacity.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SignedWitness {
    #[serde(with="crate::rpa::scalar")] pub capacity:Q,
    pub flow:Expr,pub activation:Expr,pub checks:Vec<Ref>,
}
