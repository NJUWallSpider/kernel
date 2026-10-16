use kernel_core::{codec,model::{Expr,Model,Q,Var},proof::*,verify::{verify,Limits}};
use serde_json::{json,Value};
use std::{fs,path::PathBuf,process::Command,sync::atomic::{AtomicUsize,Ordering}};
static NEXT:AtomicUsize=AtomicUsize::new(0);
struct Fixture{dir:PathBuf,work:u64}
impl Fixture{
 fn new()->Self{
  let dir=std::env::temp_dir().join(format!("rpx-mi-cli-{}-{}",std::process::id(),NEXT.fetch_add(1,Ordering::Relaxed)));fs::create_dir(&dir).unwrap();
  let q=|n:i64|Q::from_integer(n.into());
  let model=Model{name:"tiny".into(),vars:vec![Var{name:"x".into(),integer:false,lower:Some(q(0)),upper:None}],rows:vec![],objective:Expr::zero()};
  let block=Block{steps:vec![Step::Lin{id:0,kind:Kind::Le,constant:q(0),terms:vec![(Ref::VarLower(0),q(1))]}],end:End::Return{map:vec![Expr::var(0)],checks:vec![Ref::Local(0),Ref::Exact]}};
  let certificate=Certificate{forward:block.clone(),reverse:block};
  let work=verify(&model,&model,&certificate,&Limits::default()).unwrap().work;
  let bytes=codec::encode_model(&model).unwrap();for role in ["source","target"]{fs::write(dir.join(format!("{role}.mcm")),&bytes).unwrap();}
  fs::write(dir.join("proof.rpx"),codec::encode_certificate(&certificate).unwrap()).unwrap();Self{dir,work}
 }
 fn paths(&self)->Vec<String>{["source.mcm","target.mcm","proof.rpx"].iter().map(|f|self.dir.join(f).to_str().unwrap().to_owned()).collect()}
 fn run(&self,args:&[String])->(i32,Value){let out=Command::new(env!("CARGO_BIN_EXE_rpx")).arg("verify").args(args).output().unwrap();assert!(out.stderr.is_empty());(out.status.code().unwrap(),serde_json::from_slice(&out.stdout).unwrap())}
}
impl Drop for Fixture{fn drop(&mut self){fs::remove_dir_all(&self.dir).unwrap();}}
#[test]fn fixed_goal_and_limits_match_cli_and_library(){
 let f=Fixture::new();let paths=f.paths();let (code,r)=f.run(&paths);assert_eq!(code,0);assert_eq!(r["guarantee"],"MI_OPT");assert_eq!(r["statistics"]["work"],f.work);
 assert_eq!(r["limits"],json!({"work":1000000000u64,"live_facts":1000000,"depth":64}));
 for args in [vec!["--work".into(),f.work.to_string(),paths[0].clone(),paths[1].clone(),"--live-facts".into(),"1".into(),paths[2].clone()],[paths.clone(),vec!["--work".into(),f.work.to_string()]].concat()]{assert_eq!(f.run(&args).0,0);}
 for args in [[paths.clone(),vec!["--work".into(),(f.work-1).to_string()]].concat(),[paths.clone(),vec!["--live-facts".into(),"0".into()]].concat()]{let(code,r)=f.run(&args);assert_eq!(code,3);assert_eq!(r["status"],"RESOURCE_LIMIT");}
 let m=fs::read(&paths[0]).unwrap();let p=fs::read(&paths[2]).unwrap();let r=kernel_core::api::verify_bytes(&m,&m,&p,&Limits::default()).unwrap();assert_eq!(r["statistics"]["work"],f.work);assert!(r.get("read_us").is_none());
}
#[test]fn malformed_flags_and_legacy_request_are_rejected(){
 let f=Fixture::new();let paths=f.paths();
 for args in [vec![],paths[..2].to_vec(),[paths.clone(),vec!["--depth".into(),"64".into()]].concat(),[paths.clone(),vec!["--work".into(),"-1".into()]].concat(),[paths.clone(),vec!["--work".into()]].concat()]{let(code,r)=f.run(&args);assert_eq!(code,2);assert!(r["message"].as_str().unwrap().contains("usage"));}
 let request=f.dir.join("request.json");fs::write(&request,b"[]").unwrap();let(code,r)=f.run(&[paths,vec![request.to_str().unwrap().into()]].concat());assert_eq!(code,2);assert_eq!(r["status"],"INVALID");
}
#[test]fn missing_direction_never_returns_verified(){
 let f=Fixture::new();let paths=f.paths();let mut bytes=fs::read(&paths[2]).unwrap();bytes.truncate(16+(bytes.len()-16)/2);let length=bytes.len() as u64;bytes[8..16].copy_from_slice(&length.to_le_bytes());fs::write(&paths[2],bytes).unwrap();let(code,r)=f.run(&paths);assert_eq!(code,2);assert_eq!(r["status"],"INVALID");
}
