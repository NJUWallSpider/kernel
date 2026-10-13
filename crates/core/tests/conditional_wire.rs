//! Independent raw Python struct vectors; fixture bytes never use Rust encoder.
use kernel_core::{codec,rpa,verify::{verify_request,Limits}};

const HALF:&[u8]=include_bytes!("../../../tests/vectors/conditional-halfspace.rpx");
const BOTH:&[u8]=include_bytes!("../../../tests/vectors/conditional-level-halfspace.rpx");

#[test]
fn independent_conditional_bytes_bind_continuous_domain_and_level_row_order() {
    let source_bytes=include_bytes!("../../../tests/vectors/conditional-source.mcm");
    let target_bytes=include_bytes!("../../../tests/vectors/conditional-target.mcm");
    let source=codec::decode_model(source_bytes).unwrap();let target=codec::decode_model(target_bytes).unwrap();
    assert!(!source.vars[0].integer && !target.vars[0].integer);
    assert_eq!(codec::encode_model(&source).unwrap(),source_bytes);
    assert_eq!(codec::encode_model(&target).unwrap(),target_bytes);
    for (bytes,text,caller) in [(HALF,include_str!("../../../tests/vectors/conditional-halfspace.rpa"),include_str!("../../../tests/vectors/conditional-halfspace-request.json")),
        (BOTH,include_str!("../../../tests/vectors/conditional-level-halfspace.rpa"),include_str!("../../../tests/vectors/conditional-level-halfspace-request.json"))] {
        let cert=codec::decode_certificate(bytes).unwrap();assert_eq!(codec::encode_certificate(&cert).unwrap(),bytes);
        assert_eq!(rpa::assemble(text).unwrap(),cert);let request=rpa::parse_request(caller).unwrap();
        let stats=verify_request(&source,&target,&cert,&request,&Limits::default()).unwrap();assert_eq!(stats.obligations,4);
        // A caller cannot remove the condition while retaining this certificate.
        let mut unconditioned:serde_json::Value=serde_json::from_str(caller).unwrap();
        unconditioned["claims"][0].as_object_mut().unwrap().remove("input_halfspace");
        let req=rpa::parse_request(&unconditioned.to_string()).unwrap();assert!(verify_request(&source,&target,&cert,&req,&Limits::default()).is_err());
        // The same chosen witness does not prove the exact target-bound
        // expression after changing the condition, including on a level face.
        let wrong=text.replace("\"constant\":\"-1/2\"","\"constant\":\"-3/4\"");
        let wrong_cert=rpa::assemble(&wrong).unwrap();let mut wrong_request=request.clone();wrong_request.claims=wrong_cert.claims.clone();
        assert!(verify_request(&source,&target,&wrong_cert,&wrong_request,&Limits::default()).is_err());
    }
}

#[test]
fn independent_conditional_bytes_reject_truncations_versions_reserved_flags_and_option_tag() {
    let mut truncations=0;
    for bytes in [HALF,BOTH] {for n in 0..bytes.len() {
        let mut bad=bytes[..n].to_vec();if n>=16 {bad[8..16].copy_from_slice(&(n as u64).to_le_bytes());}
        assert!(codec::decode_certificate(&bad).is_err(),"truncation {n}");truncations+=1;
    }}
    assert_eq!(truncations,HALF.len()+BOTH.len());
    for (bytes,text) in [(HALF,include_str!("../../../tests/vectors/conditional-halfspace.rpa")),(BOTH,include_str!("../../../tests/vectors/conditional-level-halfspace.rpa"))] {
        for version in (0u16..10).chain([11]) {
            let mut bad=bytes.to_vec();bad[4..6].copy_from_slice(&version.to_le_bytes());assert!(codec::decode_certificate(&bad).is_err(),"version {version}");
            assert!(rpa::assemble(&text.replacen("RPA 10",&format!("RPA {version}"),1)).is_err());
        }
        for value in 16..=255 {let mut bad=bytes.to_vec();bad[20]=value;assert!(codec::decode_certificate(&bad).is_err());}
        for offset in [6,7,22,23] {for value in 1..=255 {let mut bad=bytes.to_vec();bad[offset]=value;assert!(codec::decode_certificate(&bad).is_err());}}
    }
    let manifest:serde_json::Value=serde_json::from_str(include_str!("../../../tests/vectors/conditional-manifest.json")).unwrap();
    let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/vectors");
    assert_eq!(manifest["mutations"].as_object().unwrap().len(),16);
    for (name,_) in manifest["mutations"].as_object().unwrap(){assert!(codec::decode_certificate(&std::fs::read(root.join(name)).unwrap()).is_err(),"{name}");}
}

#[test]
fn independently_written_existing_v10_none_bytes_stay_exactly_unchanged() {
    let bytes=include_bytes!("../../../tests/vectors/contract-v10.rpx");
    let cert=codec::decode_certificate(bytes).unwrap();assert_eq!(codec::encode_certificate(&cert).unwrap(),bytes);
    assert_eq!(rpa::assemble(include_str!("../../../tests/vectors/contract-v10.rpa")).unwrap(),cert);
    let bytes=include_bytes!("../../../tests/vectors/conditional-old-none.rpx");
    let cert=codec::decode_certificate(bytes).unwrap();assert_eq!(codec::encode_certificate(&cert).unwrap(),bytes);
    assert_eq!(rpa::assemble(include_str!("../../../tests/vectors/conditional-old-none.rpa")).unwrap(),cert);
    let source=codec::decode_model(include_bytes!("../../../tests/vectors/conditional-source.mcm")).unwrap();
    let target=codec::decode_model(include_bytes!("../../../tests/vectors/conditional-target.mcm")).unwrap();
    let request=rpa::parse_request(include_str!("../../../tests/vectors/conditional-old-none-request.json")).unwrap();
    let stats=verify_request(&source,&target,&cert,&request,&Limits::default()).unwrap();assert_eq!(stats.points,1);
}
