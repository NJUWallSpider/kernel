//! Two-tree proof data for fixed MILP optimization equivalence.
use crate::model::{Expr, Q};
use serde::{Deserialize, Serialize};

/// Two complete proof trees. Their domains and objective obligations are fixed.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Certificate { pub forward: Block, pub reverse: Block }
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
    Lin { id: u32, kind: Kind, #[serde(with="crate::json::scalar")] constant: Q, #[serde(with="crate::json::ref_terms")] terms: Vec<(Ref, Q)> },
    /// Integer-valued expression and LE expression must differ only by a constant.
    Round { id: u32, le: Ref, integer: Ref },
    Drop { ids: Vec<u32> },
    /// exact antisymmetry; output EQ has the positive LE's expression.
    EqPair { id: u32, positive: Ref, negative: Ref },
    /// local exhaustive cases exporting one common parent proposition.
    Cases(Box<CasesStep>),
    /// trusted Plotkin bound from checked binary domains and close-pair cliques.
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
/// independent real interval choices; all expressions use the parent scope.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct IntervalWitness{pub lower:Vec<Expr>,pub upper:Vec<Expr>,pub checks:Vec<Ref>}
/// graph and simultaneous common-source flow extension witness.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FlowWitness{pub nodes:u32,pub arcs:Vec<(u32,u32)>,pub groups:Vec<FlowGroup>}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FlowGroup{
    pub source:u32,
    #[serde(with="crate::json::expr_terms")]
    pub commodities:Vec<(u32,Q)>,
    pub flows:Vec<Expr>,
    pub nonnegative:Vec<Ref>,
    pub balances:Vec<Ref>,
}
/// jointly retain the demanded part of a nonnegative real flow.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SubflowWitness{pub nodes:u32,pub arcs:Vec<(u32,u32)>,pub groups:Vec<SubflowGroup>}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SubflowGroup{
    pub source:u32,
    #[serde(with="crate::json::expr_terms")]
    pub demands:Vec<(u32,Q)>,
    pub flows:Vec<Expr>,pub nonnegative:Vec<Ref>,pub balances:Vec<Ref>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub enum End {
    /// simultaneous demand-bounded subflows, with old-scope premises.
    SubflowLift{witness:SubflowWitness,body:Box<Block>},
    /// jointly split bounded signed real expressions into activated directions.
    SignedLift{decompositions:Vec<SignedWitness>,body:Box<Block>},
    /// jointly append optional binary menus after six old-scope premises each.
    MenuLift{menus:Vec<MenuWitness>,body:Box<Block>},
    /// jointly append independent interval choices after all pair premises.
    IntervalLift{intervals:Vec<IntervalWitness>,body:Box<Block>},
    /// jointly extend the input by real commodity flows, after all premises.
    FlowLift{witness:FlowWitness,body:Box<Block>},
    /// One common output vector; one reference for EVERY kernel-derived obligation.
    Return { map: Vec<Expr>, checks: Vec<Ref> },
    /// e<=0 and -e<=0, or e<=0 and 1-e<=0 when `integer` proves INT(e).
    Split { expression: Expr, integer: Option<Ref>, left: Box<Block>, right: Box<Block> },
    /// A checked constant-positive LE or nonzero-constant EQ closes an empty domain.
    Absurd { fact: Ref },
}

/// a bounded optional menu represented by an integer activation and index.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MenuWitness {pub maximum_index:u32,pub activation:Expr,pub index:Expr,pub checks:Vec<Ref>}

/// old-scope binary activation, real flow, nonnegative exact capacity.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SignedWitness {
    #[serde(with="crate::json::scalar")] pub capacity:Q,
    pub flow:Expr,pub activation:Expr,pub checks:Vec<Ref>,
}
