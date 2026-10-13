//! Differential audit executable, outside the production verification path.
use kernel_core::model::{parse_q, Model, Row, Var};
use kernel_core::verify::Limits;
use kernel_core::{flow, injectivity, interval, level, menu, signed};
use serde_json::{json, Value};
use std::io::{self, BufRead};

fn model(value: &Value) -> Model {
    let bound = |v: &Value| v.as_str().map(|s| parse_q(s).unwrap());
    Model {
        name: value["name"].as_str().unwrap().into(),
        vars: value["vars"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| Var {
                name: v["name"].as_str().unwrap().into(),
                integer: v["integer"].as_bool().unwrap(),
                lower: bound(&v["lower"]),
                upper: bound(&v["upper"]),
            })
            .collect(),
        rows: value["rows"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| Row {
                name: v["name"].as_str().unwrap().into(),
                expr: serde_json::from_value(v["expr"].clone()).unwrap(),
                lower: bound(&v["lower"]),
                upper: bound(&v["upper"]),
            })
            .collect(),
        objective: serde_json::from_value(value["objective"].clone()).unwrap(),
    }
}

fn execute(value: &Value) -> Result<Value, String> {
    let input = model(&value["input"]);
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
            let output = model(&value["output"]);
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
