use dedaliano_engine::solver::{linear, pdelta};
use dedaliano_engine::types::SolverInput3D;
use serde_json::{json, Value};
use std::mem;
use std::slice;

#[no_mangle]
pub extern "C" fn alloc_input(size: u32) -> u32 {
    let mut bytes = Vec::<u8>::with_capacity(size as usize);
    let ptr = bytes.as_mut_ptr();
    mem::forget(bytes);
    ptr as u32
}

#[no_mangle]
pub unsafe extern "C" fn solve_case(ptr: u32, len: u32) -> u64 {
    let input_bytes = slice::from_raw_parts(ptr as *const u8, len as usize);
    let result = std::panic::catch_unwind(|| -> Result<Value, String> {
        let request: Value = serde_json::from_slice(input_bytes).map_err(|e| e.to_string())?;
        let solver = request["solver"].as_str().ok_or("missing solver")?;
        let model: SolverInput3D = serde_json::from_value(request["input"].clone())
            .map_err(|e| e.to_string())?;
        match solver {
            "linear_3d" => linear::solve_3d(&model)
                .map(|r| serde_json::to_value(r).expect("serializable results")),
            "pdelta_3d" => pdelta::solve_pdelta_3d(&model, 100, 1.0e-9)
                .map(|r| serde_json::to_value(r).expect("serializable results")),
            other => Err(format!("unsupported solver selector: {other}")),
        }
    });
    let output = match result {
        Ok(Ok(value)) => serde_json::to_vec(&value).expect("serializable JSON value"),
        Ok(Err(error)) => serde_json::to_vec(&json!({"error": error}))
            .expect("serializable error"),
        Err(_) => br#"{"error":"Rust solver panicked"}"#.to_vec(),
    };
    let boxed = output.into_boxed_slice();
    let len = boxed.len() as u32;
    let ptr = Box::into_raw(boxed) as *mut u8 as u32;
    ((ptr as u64) << 32) | len as u64
}
