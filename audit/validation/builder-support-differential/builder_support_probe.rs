//! Differential audit executable, outside the production verification path.
use kernel_core::model::{parse_q, Model};
use kernel_core::verify::Limits;
use kernel_core::{flow, injectivity, interval, level, menu, signed};
use serde_json::{json, Value};
use std::io::{self, BufRead};

fn execute(value: &Value) -> Result<Value, String> {
    let input: Model = serde_json::from_value(value["input"].clone()).unwrap();
    let limits = Limits {
        work: value["work"].as_u64().unwrap_or(Limits::default().work),
        ..Limits::default()
    };
    macro_rules! lift {
        ($module:ident) => {{
            let witness = serde_json::from_value(value["witness"].clone()).unwrap();
            let extension = $module::prepare_unchecked_extension(&input, &witness, &limits)?;
            let premises: Vec<_> = extension.premises.iter().map(|p|
                json!({"kind":p.kind,"expression":p.expression,"reference":p.reference})).collect();
            Ok(json!({"model":extension.model,"statistics":extension.statistics,"premises":premises}))
        }};
    }
    match value["kind"].as_str().unwrap() {
        "flow" => lift!(flow),
        "interval" => {
            let witness: Vec<_> = serde_json::from_value(value["witness"].clone()).unwrap();
            let e = interval::prepare_unchecked_extension(&input, &witness, &limits)?;
            let p: Vec<_> = e
                .premises
                .iter()
                .map(|p| json!({"kind":p.kind,"expression":p.expression,"reference":p.reference}))
                .collect();
            Ok(json!({"model":e.model,"statistics":e.statistics,"premises":p}))
        }
        "menu" => {
            let witness: Vec<_> = serde_json::from_value(value["witness"].clone()).unwrap();
            let e = menu::prepare_unchecked_extension(&input, &witness, &limits)?;
            let p: Vec<_> = e
                .premises
                .iter()
                .map(|p| json!({"kind":p.kind,"expression":p.expression,"reference":p.reference}))
                .collect();
            Ok(json!({"model":e.model,"statistics":e.statistics,"premises":p}))
        }
        "signed" => {
            let witness: Vec<_> = serde_json::from_value(value["witness"].clone()).unwrap();
            let e = signed::prepare_unchecked_extension(&input, &witness, &limits)?;
            let p: Vec<_> = e
                .premises
                .iter()
                .map(|p| json!({"kind":p.kind,"expression":p.expression,"reference":p.reference}))
                .collect();
            Ok(json!({"model":e.model,"statistics":e.statistics,"premises":p}))
        }
        "injectivity" => {
            let output = serde_json::from_value(value["output"].clone()).unwrap();
            let map: Vec<_> = serde_json::from_value(value["map"].clone()).unwrap();
            let e = injectivity::prepare_domain(&input, &output, &map, &limits)?;
            Ok(json!({"model":e.model,"statistics":e.statistics,"equalities":e.equalities}))
        }
        "level" => {
            let q = parse_q(value["level"].as_str().unwrap())?;
            let e = level::prepare_domain(&input, &q, &limits)?;
            Ok(json!({"model":e.model,"statistics":e.statistics,"equality_row":e.equality_row}))
        }
        _ => panic!("unsupported audit kind"),
    }
}

fn main() {
    for line in io::stdin().lock().lines() {
        let value: Value = serde_json::from_str(&line.unwrap()).unwrap();
        let result = match execute(&value) {
            Ok(data) => json!({"status":"PREPARED","data":data}),
            Err(error) => json!({"status":error.split_whitespace().next().unwrap(),"error":error}),
        };
        println!("{}", serde_json::to_string(&result).unwrap());
    }
}
