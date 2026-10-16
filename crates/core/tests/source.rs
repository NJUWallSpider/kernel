use kernel_core::{codec,compiler,lp,proof::End,rpa,rpa_source,verify::{verify,Limits}};
use std::{fs,path::Path};
#[test]
fn documented_sources_bind_roundtrip_and_certify_both_directions(){
    let root=Path::new(env!("CARGO_MANIFEST_DIR")).join("../../docs/rpx/examples");
    for name in ["redundant","elimination","piecewise"]{
        let d=root.join(name);
        let source=lp::parse_lp(&fs::read_to_string(d.join("source.lp")).unwrap()).unwrap();
        let target=lp::parse_lp(&fs::read_to_string(d.join("target.lp")).unwrap()).unwrap();
        let c=rpa_source::assemble_with_models(&fs::read_to_string(d.join("proof.rpas")).unwrap(),&source,&target).unwrap();
        assert_eq!(c,rpa::assemble(&fs::read_to_string(d.join("proof.rpa")).unwrap()).unwrap());
        verify(&source,&target,&c,&Limits::default()).unwrap();
        let text=rpa_source::disassemble_with_models(&c,&source,&target).unwrap();
        assert_eq!(rpa_source::assemble_with_models(&text,&source,&target).unwrap(),c);
        assert!(rpa_source::assemble_with_models(&text.replace("objective.non_increasing","objective.equal"),&source,&target).is_err());
        assert!(rpa_source::assemble_with_models(&text.replace("certificate {","certificate { claims: [],"),&source,&target).is_err());
        let bytes=codec::encode_certificate(&c).unwrap();assert_eq!(bytes[4],11);
        assert_eq!(codec::decode_certificate(&bytes).unwrap(),c);
    }
}
#[test]
fn planning_has_no_domain_or_objective_switch(){
    let model=lp::parse_lp("Minimize\n obj: x\nSubject To\nBounds\n 0 <= x <= 1\nGeneral\n x\nEnd\n").unwrap();
    let plan=compiler::parse_return_plan_json(r#"{"map":[{"constant":"0","terms":[[0,"1"]]}]}"#).unwrap();
    let goals=compiler::plan_return(&model,&model,&plan,&Limits::default()).unwrap();
    assert_eq!(goals.len(),4);assert_eq!(goals[2].kind,kernel_core::proof::Kind::Int);assert_eq!(goals[3].kind,kernel_core::proof::Kind::Le);
    for field in ["claim","inverse_map","improvement","compositions"]{
        let mut value=serde_json::json!({"map":[]});value[field]=serde_json::json!({});assert!(compiler::parse_return_plan_json(&value.to_string()).is_err());
    }
}
#[test]
fn new_source_rejects_legacy_headers_and_extra_terminal_checks(){
    let d=Path::new(env!("CARGO_MANIFEST_DIR")).join("../../docs/rpx/examples/redundant");
    let text=fs::read_to_string(d.join("proof.rpa")).unwrap();
    for v in 1..11{assert!(rpa::assemble(&text.replacen("RPA 11",&format!("RPA {v}"),1)).is_err());}
    let s=lp::parse_lp(&fs::read_to_string(d.join("source.lp")).unwrap()).unwrap();let t=lp::parse_lp(&fs::read_to_string(d.join("target.lp")).unwrap()).unwrap();
    let mut c=rpa::assemble(&text).unwrap();if let End::Return{checks,..}=&mut c.reverse.end{checks.push(kernel_core::proof::Ref::Exact);}
    assert!(verify(&s,&t,&c,&Limits::default()).unwrap_err().contains("surplus"));
}
