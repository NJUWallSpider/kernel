//! Vectors are written directly by Python struct, independently of Rust.
use kernel_core::{codec,rpa,verify::{verify_request,Limits}};

const BYTES:&[u8]=include_bytes!("../../../tests/vectors/contract-v10.rpx");
#[test]
fn independent_combined_image_and_improvement_bytes_match_text_and_verify() {
    let source_bytes=include_bytes!("../../../tests/vectors/contract-v10-source.mcm");
    let target_bytes=include_bytes!("../../../tests/vectors/contract-v10-target.mcm");
    let source=codec::decode_model(source_bytes).unwrap();
    let target=codec::decode_model(target_bytes).unwrap();
    assert_eq!(codec::encode_model(&source).unwrap(),source_bytes);
    assert_eq!(codec::encode_model(&target).unwrap(),target_bytes);
    let cert=codec::decode_certificate(BYTES).unwrap();
    assert_eq!(codec::encode_certificate(&cert).unwrap(),BYTES);
    assert_eq!(rpa::assemble(include_str!("../../../tests/vectors/contract-v10.rpa")).unwrap(),cert);
    let req=rpa::parse_request(include_str!("../../../tests/vectors/contract-v10-request.json")).unwrap();
    let stats=verify_request(&source,&target,&cert,&req,&Limits::default()).unwrap();
    assert_eq!(stats.improvements,2);
    assert_eq!(stats.points,1);
    assert!(verify_request(&target,&source,&cert,&req,&Limits::default()).is_err());
}

#[test]
fn independent_combined_vector_rejects_all_truncations_versions_and_reserved_flags() {
    for n in 0..BYTES.len() {
        let mut bad=BYTES[..n].to_vec();
        if n>=16 {bad[8..16].copy_from_slice(&(n as u64).to_le_bytes());}
        assert!(codec::decode_certificate(&bad).is_err(),"truncation {n}");
    }
    for version in (0u16..10).chain([11]) {
        let mut bad=BYTES.to_vec();bad[4..6].copy_from_slice(&version.to_le_bytes());
        assert!(codec::decode_certificate(&bad).is_err(),"version {version}");
        assert!(rpa::assemble(&include_str!("../../../tests/vectors/contract-v10.rpa")
            .replacen("RPA 10",&format!("RPA {version}"),1)).is_err());
    }
    let manifest:serde_json::Value=serde_json::from_str(include_str!("../../../tests/vectors/contract-v10-manifest.json")).unwrap();
    let mutations=manifest["negative_mutations"].as_object().unwrap();
    assert_eq!(mutations.len(),20);
    let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/vectors");
    for (name,recipe) in mutations {
        let bytes=std::fs::read(root.join(name)).unwrap();
        let mut expected=BYTES.to_vec();expected[recipe["offset"].as_u64().unwrap() as usize]=recipe["value"].as_u64().unwrap() as u8;
        assert_eq!(bytes,expected);
        assert!(codec::decode_certificate(&bytes).is_err(),"flags {name}");
    }
    // Exhaust every forbidden value of each new flag/reserved byte, not only
    // the representative mutations persisted as separate binary files.
    let offsets=&manifest["offsets"];
    let mut checked=0;
    for (key,largest_valid) in [("point_flags",1),("improvement_1_flags",3),
        ("improvement_2_flags",3),("predicate_margin_tag",1),("constant_margin_tag",1)] {
        let offset=offsets[key].as_u64().unwrap() as usize;
        for field in 0..4 {
            let first=if field==0 {largest_valid+1}else{1};
            for value in first..=255 {
                let mut bad=BYTES.to_vec();bad[offset+field]=value as u8;
                assert!(codec::decode_certificate(&bad).is_err(),"{key} field{field} value{value}");
                checked+=1;
            }
        }
    }
    for offset in [6,7] {for value in 1..=255 {
        let mut bad=BYTES.to_vec();bad[offset]=value;
        assert!(codec::decode_certificate(&bad).is_err());checked+=1;
    }}
    assert_eq!(checked,5601);
}
