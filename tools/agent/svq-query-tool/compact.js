/**
 * Pure result compaction for the constrained svq_query DSH tool.
 *
 * No I/O, no imports: every function takes a raw `sv_query --json` payload
 * and returns the compact object rendered to the agent. Malformed or missing
 * payloads throw an explicit Error instead of degrading to empty lists.
 */

export const INTENTS = ["fanin", "fanout", "neighbors", "path"];

function fail(message) {
  throw new Error(`svq compact: ${message}`);
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function failureDetail(payload) {
  const err = payload.error;
  if (typeof err === "string" && err) return err;
  if (isPlainObject(err)) return err.message || JSON.stringify(err);
  return "ok=false";
}

function assertSuccess(payload, label) {
  if (!isPlainObject(payload)) {
    fail(`${label} payload must be an object`);
  }
  if (payload.ok === false) {
    fail(`${label} returned failure: ${failureDetail(payload)}`);
  }
}

function signalIds(payload, field, label) {
  assertSuccess(payload, label);
  if (!isPlainObject(payload.result)) {
    fail(`${label} payload is missing result object`);
  }
  const signals = payload.result.signals;
  if (!Array.isArray(signals)) {
    fail(`${label} payload is missing result.signals array`);
  }
  if (signals.length === 0) return [];
  const first = signals[0];
  if (!isPlainObject(first)) {
    fail(`${label} payload result.signals[0] must be an object`);
  }
  const rows = first[field];
  if (!Array.isArray(rows)) {
    fail(`${label} payload is missing result.signals[0].${field} array`);
  }
  return rows.map((row, i) => {
    if (!isPlainObject(row) || typeof row.id !== "string") {
      fail(`${label} payload result.signals[0].${field}[${i}] is missing string id`);
    }
    return row.id;
  });
}

/** fanin: drivers -> compact driver ids. */
export function compactFanin(payload, meta = {}) {
  const drivers = signalIds(payload, "drivers", "fanin");
  return {
    ok: true, intent: "fanin", snapshot: meta.snapshot,
    signal: meta.signal,
    drivers,
    count: drivers.length,
  };
}

/** fanout: loads -> compact load ids. */
export function compactFanout(payload, meta = {}) {
  const loads = signalIds(payload, "loads", "fanout");
  return {
    ok: true, intent: "fanout", snapshot: meta.snapshot,
    signal: meta.signal,
    loads,
    count: loads.length,
  };
}

/** neighbors: combine one drivers payload and one loads payload. */
export function compactNeighbors(driverPayload, loadPayload, meta = {}) {
  const drivers = signalIds(driverPayload, "drivers", "neighbors drivers");
  const loads = signalIds(loadPayload, "loads", "neighbors loads");
  return {
    ok: true, intent: "neighbors", snapshot: meta.snapshot,
    signal: meta.signal,
    drivers,
    loads,
    count: drivers.length + loads.length,
  };
}

/** path: canonical node path + hop count. */
export function compactPath(payload, meta = {}) {
  if (!isPlainObject(payload)) {
    fail("path payload must be an object");
  }
  if (payload.path !== undefined && payload.path !== null && !Array.isArray(payload.path)) {
    fail("path payload path must be an array or null");
  }
  if (payload.hop_count !== undefined && payload.hop_count !== null
      && !Number.isInteger(payload.hop_count)) {
    fail("path payload hop_count must be an integer or null");
  }
  return {
    ok: payload.ok !== false,
    intent: "path", snapshot: meta.snapshot,
    path: payload.path || [],
    count: payload.hop_count ?? null,
  };
}

/**
 * Dispatch by intent.
 *
 * payload is the raw response for fanin/fanout/path, and
 * `{ drivers, loads }` for neighbors.
 */
export function compactResult(intent, payload, meta = {}) {
  if (!INTENTS.includes(intent)) {
    fail(`unknown intent: ${intent}`);
  }
  if (intent === "fanin") return compactFanin(payload, meta);
  if (intent === "fanout") return compactFanout(payload, meta);
  if (intent === "path") return compactPath(payload, meta);
  if (!isPlainObject(payload)) {
    fail("neighbors payload must be { drivers, loads }");
  }
  return compactNeighbors(payload.drivers, payload.loads, meta);
}
