//! `rpx`: command-line shell over [`kernel_core::api`].
//!
//! Argument parsing, stdout and exit codes only. Every operation, every status
//! classification and every report field lives in the library façade, so a
//! programmatic caller and this binary cannot drift apart.

use kernel_core::{api, verify::Limits};
use std::env;

const USAGE: &str = "INVALID usage: rpx canonical input.mps output.mcm | compile [--max-json-bytes <u64>] certificate.json proof.rpx | plan-return input.mcm output.mcm plan.json obligations.json | resolve-return input.mcm output.mcm spec.json checks.json | prepare-extension input.mcm spec.json output.json | assemble input.rpa output.rpx | disassemble input.rpx output.rpa | verify [--work <u64>] [--live-facts <usize>] source.mcm target.mcm proof.rpx (options may appear anywhere after verify) | inspect-model model.mcm | export-model model.mcm output.json";

fn compile_args(a: &[String]) -> Result<([&str; 2], api::CompileOptions), String> {
    let mut options = api::CompileOptions::default();
    let mut supplied_limit = false;
    let mut paths = [""; 2];
    let mut count = 0;
    let mut args = a.iter();
    while let Some(arg) = args.next() {
        if arg == "--max-json-bytes" {
            if supplied_limit { return Err(USAGE.into()); }
            let text = args.next().ok_or(USAGE)?;
            if text.is_empty() || !text.bytes().all(|byte| byte.is_ascii_digit()) {
                return Err(USAGE.into());
            }
            let limit = text.parse::<u64>().map_err(|_| USAGE)?;
            options = api::CompileOptions::new(limit)?;
            supplied_limit = true;
        } else {
            if arg.starts_with("--") || count == paths.len() { return Err(USAGE.into()); }
            paths[count] = arg;
            count += 1;
        }
    }
    if count != paths.len() { return Err(USAGE.into()); }
    Ok((paths, options))
}

fn verify_args(a: &[String]) -> Result<([&str; 3], Limits), String> {
    let mut limits = Limits::default();
    let mut paths = [""; 3];
    let mut count = 0;
    let mut args = a.iter();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--work" => limits.work = args.next().ok_or(USAGE)?.parse().map_err(|_| USAGE)?,
            "--live-facts" => limits.live_facts = args.next().ok_or(USAGE)?.parse().map_err(|_| USAGE)?,
            path => {
                if path.starts_with("--") || count == paths.len() {
                    return Err(USAGE.into());
                }
                paths[count] = path;
                count += 1;
            }
        }
    }
    if count != 3 {
        return Err(USAGE.into());
    }
    Ok((paths, limits))
}

fn run(args: &[String]) -> Result<serde_json::Value, api::Error> {
    match args.get(1).map(String::as_str) {
        Some("canonical") if args.len() == 4 => api::canonicalize_path(&args[2], &args[3]),
        Some("compile") => {
            let (paths, options) = compile_args(&args[2..]).map_err(api::Error::from_message)?;
            api::compile_certificate_paths_with_options(paths[0], paths[1], &options)
        },
        Some("plan-return") if args.len() == 6 => api::plan_return_paths(&args[2], &args[3], &args[4], &args[5]),
        Some("resolve-return") if args.len() == 6 => api::resolve_return_paths(&args[2], &args[3], &args[4], &args[5]),
        Some("prepare-extension") if args.len() == 5 => kernel_core::authoring::prepare_extension_paths(&args[2], &args[3], &args[4]),
        Some("assemble") if args.len() == 4 => api::assemble_paths(&args[2], &args[3]),
        Some("disassemble") if args.len() == 4 => api::disassemble_paths(&args[2], &args[3]),
        Some("verify") => {
            let (paths, limits) = verify_args(&args[2..]).map_err(api::Error::from_message)?;
            api::verify_paths(paths[0], paths[1], paths[2], &limits).map_err(|error| error.with_limits(limits))
        }
        Some("inspect-model") if args.len() == 3 => api::inspect_model_path(&args[2]),
        Some("export-model") if args.len() == 4 => api::export_model_paths(&args[2], &args[3]),
        _ => Err(api::Error::from_message(USAGE.into())),
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let (value, code) = match run(&args) {
        Ok(value) => (value, api::Status::Verified.exit_code()),
        Err(error) => {
            let code = error.status().exit_code();
            (error.to_json(), code)
        }
    };
    println!("{value}");
    std::process::exit(code);
}
