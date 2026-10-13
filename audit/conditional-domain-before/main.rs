use kernel_core::{codec,model,rpa,verify::{self,Limits}};
use serde_json::json;
use std::{env,fs,io::{Read,Write},path::Path,time::Instant};
const FILE_LIMIT:u64=512*1024*1024;
const USAGE:&str="INVALID usage: rpx canonical input.mps output.mcm | assemble input.rpa output.rpx | disassemble input.rpx output.rpa | verify [--work <u64>] [--live-facts <usize>] source.mcm target.mcm proof.rpx request.json (options may appear anywhere after verify) | inspect-model model.mcm";
fn verify_args(a:&[String])->Result<([&str;4],Limits),String>{
    let mut limits=Limits::default();
    let mut paths=["";4];let mut count=0;
    let mut args=a.iter();
    while let Some(arg)=args.next(){
        match arg.as_str(){
            "--work"=>limits.work=args.next().ok_or(USAGE)?.parse().map_err(|_|USAGE)?,
            "--live-facts"=>limits.live_facts=args.next().ok_or(USAGE)?.parse().map_err(|_|USAGE)?,
            path=>{
                if path.starts_with("--")||count==paths.len(){return Err(USAGE.into());}
                paths[count]=path;count+=1;
            }
        }
    }
    if count!=paths.len(){return Err(USAGE.into());}
    Ok((paths,limits))
}
fn limits_json(limits:&Limits)->serde_json::Value{
    json!({"work":limits.work,"live_facts":limits.live_facts,"depth":limits.depth})
}
fn read(path:&str)->Result<Vec<u8>,String>{
    let f=fs::File::open(path).map_err(|e|format!("IO_ERROR {path}: {e}"))?;
    let len=f.metadata().map_err(|e|format!("IO_ERROR {e}"))?.len();
    if len>FILE_LIMIT{return Err("RESOURCE_LIMIT input file bytes".into());}
    let mut b=Vec::new();b.try_reserve(len as usize).map_err(|_|"RESOURCE_LIMIT file allocation")?;
    f.take(FILE_LIMIT+1).read_to_end(&mut b).map_err(|e|format!("IO_ERROR {e}"))?;
    if b.len() as u64>FILE_LIMIT{return Err("RESOURCE_LIMIT input file bytes".into());}Ok(b)
}
fn text(path:&str)->Result<String,String>{String::from_utf8(read(path)?).map_err(|_|"INVALID non-UTF8 text".into())}
fn write(path:&str,b:&[u8])->Result<(),String>{
    // Only replace output after all parsing/encoding has succeeded.
    let p=Path::new(path);if let Some(parent)=p.parent(){if !parent.as_os_str().is_empty(){fs::create_dir_all(parent).map_err(|e|format!("IO_ERROR {e}"))?;}}
    fs::write(p,b).map_err(|e|format!("IO_ERROR {e}"))
}
fn run(a:&[String],effective_limits:&mut Option<Limits>)->Result<serde_json::Value,String>{
    let start=Instant::now();
    match a.get(1).map(String::as_str) {
        Some("canonical") if a.len()==4=>{
            let input=text(&a[2])?;let read_us=start.elapsed().as_micros();
            let model=if Path::new(&a[2]).extension().is_some_and(|s|s.eq_ignore_ascii_case("lp")) { kernel_core::lp::parse_lp(&input)? } else { model::parse_mps(&input)? };let parse_us=start.elapsed().as_micros()-read_us;
            let encoded=codec::encode_model(&model)?;write(&a[3],&encoded)?;
            Ok(json!({"status":"CANONICALIZED","variables":model.vars.len(),"rows":model.rows.len(),"mcm_bytes":encoded.len(),"read_us":read_us,"parse_us":parse_us,"total_us":start.elapsed().as_micros()}))
        },
        Some("assemble") if a.len()==4=>{
            let cert=rpa::assemble(&text(&a[2])?)?;let encoded=codec::encode_certificate(&cert)?;write(&a[3],&encoded)?;
            Ok(json!({"status":"ASSEMBLED","rpx_bytes":encoded.len(),"total_us":start.elapsed().as_micros()}))
        },
        Some("disassemble") if a.len()==4=>{
            let cert=codec::decode_certificate(&read(&a[2])?)?;write(&a[3],rpa::disassemble(&cert)?.as_bytes())?;Ok(json!({"status":"DISASSEMBLED"}))
        },
        Some("verify")=>{
            let (paths,limits)=verify_args(&a[2..])?;
            *effective_limits=Some(limits);
            let limits=effective_limits.as_ref().unwrap();
            let s=read(paths[0])?;let t=read(paths[1])?;let p=read(paths[2])?;let request=text(paths[3])?;
            let read_us=start.elapsed().as_micros();
            let source=codec::decode_model(&s)?;let target=codec::decode_model(&t)?;
            let models_us=start.elapsed().as_micros()-read_us;
            let cert=codec::decode_certificate(&p)?;
            let requested=rpa::parse_request(&request)?;
            let proof_decode_us=start.elapsed().as_micros()-read_us-models_us;
            let statistics=verify::verify_request(&source,&target,&cert,&requested,limits)?;
            let total_us=start.elapsed().as_micros();
            let mut result=json!({"status":"VERIFIED","claims":requested.claims.len(),"points":requested.points.len(),"bijections":requested.bijections.len(),"statistics":statistics,"limits":limits_json(limits),"read_us":read_us,"model_decode_us":models_us,"proof_decode_us":proof_decode_us,"execute_us":total_us-read_us-models_us-proof_decode_us,"total_us":total_us});
            if !requested.improvements.is_empty(){result["improvements"]=json!(requested.improvements.len());}
            Ok(result)
        },
        Some("inspect-model") if a.len()==3=>{
            let m=codec::decode_model(&read(&a[2])?)?;
            Ok(json!({"status":"INSPECTED","name":m.name,"variables":m.vars.len(),"rows":m.rows.len(),"integers":m.vars.iter().filter(|v|v.integer).count(),"nonzeros":m.rows.iter().map(|r|r.expr.terms.len()).sum::<usize>()+m.objective.terms.len()}))
        },
        _=>Err(USAGE.into())
    }
}
fn main(){
    let a:Vec<String>=env::args().collect();
    let mut effective_limits=None;
    let (value,code)=match run(&a,&mut effective_limits){Ok(v)=>(v,0),Err(e)=>{let (status,code)=if e.starts_with("IO_ERROR"){("IO_ERROR",4)}else if e.starts_with("RESOURCE_LIMIT"){("RESOURCE_LIMIT",3)}else{("INVALID",2)};let mut value=json!({"status":status,"message":e});if let Some(limits)=effective_limits{value["limits"]=limits_json(&limits);}(value,code)}};
    let mut out=std::io::stdout().lock();let _=writeln!(out,"{value}");std::process::exit(code);
}
