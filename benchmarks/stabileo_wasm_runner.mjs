// Run one Stabileo solve in a fresh WASM instance. Input is JSON on stdin.
import { readFileSync } from 'node:fs';

const input = readFileSync(0);
const wasm = readFileSync(process.argv[2]);
const module = await WebAssembly.compile(wasm);
const imports = {};
// The crate also exports wasm-bindgen UI entrypoints. Our raw JSON adapter never
// uses them. Fail if a benchmark reaches any of those JS-dependent functions;
// never substitute a numerical result or silently ignore a solver callback.
for (const entry of WebAssembly.Module.imports(module)) {
  if (entry.kind !== 'function') throw new Error(`Unsupported WASM import: ${entry.kind}`);
  imports[entry.module] ??= {};
  imports[entry.module][entry.name] = () => {
    throw new Error(`Unexpected JS-dependent engine call: ${entry.module}.${entry.name}`);
  };
}
const instance = await WebAssembly.instantiate(module, imports);
const ptr = instance.exports.alloc_input(input.length);
new Uint8Array(instance.exports.memory.buffer, ptr, input.length).set(input);
const packed = instance.exports.solve_case(ptr, input.length);
const outputPtr = Number(packed >> 32n);
const outputLength = Number(packed & 0xffffffffn);
const output = new Uint8Array(instance.exports.memory.buffer, outputPtr, outputLength);
process.stdout.write(Buffer.from(output));
