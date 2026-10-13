use kernel_core::{codec, model::{Expr,Model}, rpa, verify::{verify_request,Limits}};

fn nested(levels:usize)->String {
    let mut block=r#"{"steps":[],"end":{"Return":{"map":[],"checks":[]}}}"#.to_string();
    for _ in 0..levels {
        block=format!(r#"{{"steps":[],"end":{{"IntervalLift":{{"intervals":[],"body":{block}}}}}}}"#);
    }
    format!(r#"RPA 5
{{"claims":[{{"reverse":false,"input_integers":false,"output_integers":false,"objective":"None","projection":[],"inverse":null}}],"blocks":[{block}]}}"#)
}

#[test]
fn json_nesting_exhaustion_is_a_resource_outcome_below_kernel_depth_limit() {
    let empty=Model{name:"empty".into(),vars:vec![],rows:vec![],objective:Expr::zero()};
    let mut last_good=None;
    let mut first_bad=None;
    for levels in 0..64 {
        match rpa::assemble(&nested(levels)) {
            Ok(cert)=>last_good=Some((levels,cert)),
            Err(error)=>{
                assert!(error.starts_with("RESOURCE_LIMIT RPA: recursion limit exceeded"),"{levels}: {error}");
                first_bad=Some(levels);break;
            }
        }
    }
    let (levels,cert)=last_good.expect("a shallow certificate must assemble");
    assert_eq!(first_bad,Some(levels+1));
    assert!(levels+2<Limits::default().depth,"JSON capacity is separate from proof depth");
    let request=kernel_core::proof::Request{improvements:vec![], claims:cert.claims.clone(),points:vec![],bijections:vec![]};
    let bytes=codec::encode_certificate(&cert).unwrap();
    let cert=codec::decode_certificate(&bytes).unwrap();
    verify_request(&empty,&empty,&cert,&request,&Limits::default()).unwrap();
}

#[test]
fn malformed_json_and_unknown_fields_remain_invalid() {
    for text in ["RPA 5\n{", "RPA 5\n{\"recursion limit exceeded\":0}", "RPA 5\n{\"claims\":false,\"blocks\":[]}"] {
        assert!(rpa::assemble(text).unwrap_err().starts_with("INVALID"));
    }
    for text in ["{", "{\"recursion limit exceeded\":0}", "[false]"] {
        assert!(rpa::parse_request(text).unwrap_err().starts_with("INVALID"));
    }
}
