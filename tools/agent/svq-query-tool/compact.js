/**
 * Pure result compaction for the constrained svq_query DSH tool.
 *
 * No I/O, no imports: every function takes a raw `sv_query --json` payload
 * and returns the compact object rendered to the agent. Malformed or missing
 * payloads throw an explicit Error instead of degrading to empty lists.
 */

export const INTENTS = ["fanin", "fanout", "neighbors", "path", "neighborhood", "evidence"];

function fail(message, payload = undefined) {
  const err = new Error(`svq compact: ${message}`);
  err.payload = payload;
  throw err;
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
    fail(`${label} returned failure: ${failureDetail(payload)}`, payload);
  }
}

function signalRows(payload, field, label) {
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
    return row;
  });
}

function detailRows(rows) {
  return rows.map((row) => ({
    id: row.id,
    kind: row.kind ?? null,
    condition: row.condition ?? "",
    distance: row.distance ?? null,
  }));
}

/** fanin: drivers -> compact driver ids. */
export function compactFanin(payload, meta = {}) {
  const rows = signalRows(payload, "drivers", "fanin");
  const drivers = rows.map((r) => r.id);
  const out = {
    ok: true, status: "ok", found: true, intent: "fanin", snapshot: meta.snapshot,
    signal: meta.signal,
    drivers,
    count: drivers.length,
  };
  if (meta.details) out.driver_details = detailRows(rows);
  return out;
}

/** fanout: loads -> compact load ids. */
export function compactFanout(payload, meta = {}) {
  const rows = signalRows(payload, "loads", "fanout");
  const loads = rows.map((r) => r.id);
  const out = {
    ok: true, status: "ok", found: true, intent: "fanout", snapshot: meta.snapshot,
    signal: meta.signal,
    loads,
    count: loads.length,
  };
  if (meta.details) out.load_details = detailRows(rows);
  return out;
}

/** neighbors: combine one drivers payload and one loads payload. */
export function compactNeighbors(driverPayload, loadPayload, meta = {}) {
  const driverRows = signalRows(driverPayload, "drivers", "neighbors drivers");
  const loadRows = signalRows(loadPayload, "loads", "neighbors loads");
  const drivers = driverRows.map((r) => r.id);
  const loads = loadRows.map((r) => r.id);
  const out = {
    ok: true, status: "ok", found: true, intent: "neighbors", snapshot: meta.snapshot,
    signal: meta.signal,
    drivers,
    loads,
    count: drivers.length + loads.length,
  };
  if (meta.details) {
    out.driver_details = detailRows(driverRows);
    out.load_details = detailRows(loadRows);
  }
  return out;
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
  if (Array.isArray(payload.all_paths)) {
    const variants = payload.all_paths.filter((x) => Array.isArray(x) && x.length > 0);
    if (variants.length === 0) {
      return { ok: false, status: "not_found", found: false, intent: "path",
               snapshot: meta.snapshot, path: [], count: null,
               variants: 0, truncated: !!payload.truncated,
               error: { code: "E_PATH_NOT_FOUND", message: "no directed path found" } };
    }
    // Default: shortest path. `granular` opts into the most-node variant
    // (used by deep-chain tasks); ties are lexicographic.
    if (meta.granular) {
      variants.sort((a, b) => b.length - a.length || a.join("\u0000").localeCompare(b.join("\u0000")));
    } else {
      variants.sort((a, b) => a.length - b.length || a.join("\u0000").localeCompare(b.join("\u0000")));
    }
    const path = variants[0];
    return {
      ok: payload.ok !== false, status: "ok", found: true,
      intent: "path", snapshot: meta.snapshot,
      path, count: path.length - 1,
      variants: variants.length, truncated: !!payload.truncated,
    };
  }
  if (payload.found === false) {
    return { ok: false, status: "not_found", found: false, intent: "path",
             snapshot: meta.snapshot, path: [], count: null,
             error: { code: "E_PATH_NOT_FOUND", message: "no directed path found" } };
  }
  return {
    ok: payload.ok !== false, status: "ok", found: true,
    intent: "path", snapshot: meta.snapshot,
    path: payload.path || [],
    count: payload.hop_count ?? null,
  };
}

/** Normalize branch conditions to unique condition atoms.
 *
 * The graph records both a condition and its negation (`sel[0]`,
 * `!(sel[0])`). The atom is the expression under the negation, not the branch
 * polarity. This is a presentation helper, not a semantic solver.
 */
export function conditionAtoms(conditions) {
  if (!Array.isArray(conditions)) {
    fail("conditions must be an array");
  }
  const out = [];
  const seen = new Set();
  for (const raw of conditions) {
    if (typeof raw !== "string") continue;
    let atom = raw.trim();
    if (!atom) continue;
    if (atom.startsWith("!")) atom = atom.slice(1).trim();
    while (atom.startsWith("(") && atom.endsWith(")")) {
      atom = atom.slice(1, -1).trim();
    }
    if (!atom || seen.has(atom)) continue;
    seen.add(atom);
    out.push(atom);
  }
  return out;
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
