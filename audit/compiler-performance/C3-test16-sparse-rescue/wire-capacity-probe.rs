//! Read-only typed/wire capacity counterexample. Compile against the current
//! release core with rustc --edition=2024 --extern kernel_core=target/release/
//! libkernel_core.rlib -L dependency=target/release/deps; use a temporary output.
use kernel_core::{codec, model::{Expr, Model, Row, Var, parse_q}, proof::*,
                  verify::{verify_request, Limits}};

fn main() {
    let zero = parse_q("0").unwrap();
    let scalar = parse_q(&format!("1{}", "0".repeat(3000))).unwrap();
    let wide = &scalar * &scalar;
    let model = Model {name:"wire-capacity".into(), vars:vec![Var {
        name:"x".into(), integer:false, lower:Some(zero.clone()), upper:Some(zero.clone())}],
        rows:vec![Row {name:"fixed".into(), expr:Expr::var(0), lower:Some(zero.clone()),
                      upper:Some(zero.clone())}], objective:Expr::zero()};
    let claim = Claim {reverse:false, input_integers:false, output_integers:false,
        objective:Objective::None, projection:vec![], affine_projection:vec![], inverse:None,
        input_objective_lower:None, input_objective_level:None, input_halfspace:None};
    let cert = Certificate {claims:vec![claim.clone()], blocks:vec![Block {
        steps:vec![Step::Lin {id:0, kind:Kind::Eq, constant:zero,
                             terms:vec![(Ref::RowEq(0),wide.clone())]}],
        end:End::Return {map:vec![Expr::var(0)],
                        checks:vec![Ref::VarLower(0),Ref::VarUpper(0),Ref::RowEq(0)]}}],
        ..Certificate::default()};
    let request = Request {claims:vec![claim], ..Request::default()};
    println!("scalar_digits={} scalar_bits={} frozen_wire_bits={} intermediate_bits={} typed_kernel={:?} frozen_encoder={:?}",
        wide.to_string().len(), wide.numer().bits(), codec::MAX_INTEGER_BYTES*8,
        kernel_core::model::MAX_Q_BITS,
        verify_request(&model,&model,&cert,&request,&Limits::default()).map(|s|s.work),
        codec::encode_certificate(&cert).map(|b|b.len()));
}
