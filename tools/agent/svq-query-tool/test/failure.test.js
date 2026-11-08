import test from "node:test";
import assert from "node:assert/strict";

import {
  FAILURE_STATUSES,
  classifyFailure,
  failureCode,
  failureDetail,
  failureParts,
  failureResult,
} from "../failure.js";

const ARGS = { intent: "fanin", snapshot: "ad_axi", signal: "top.u_axi.araddr" };

/**
 * Real `sv_query trace fanin` envelope for a signal that is not in the graph.
 * The row under `result.signals[]` carries `resolution`/`suggestions`; the
 * entry under `errors[]` carries the stable `error_code`.
 */
const NOT_FOUND_PAYLOAD = {
  ok: false,
  command: "trace_fanin",
  result: {
    signals: [{
      signal: "top.ghost",
      index: 0,
      drivers: [],
      count: 0,
      error: "signal 'top.ghost' not found in graph",
      resolved_signal: null,
      resolution: "not_found",
      candidates: [],
      suggestions: ["top.ghost_int"],
      top_ambiguous: false,
    }],
    total_signals: 1,
    total_count: 0,
    failed_signals: 1,
  },
  errors: [{
    signal: "top.ghost",
    index: 0,
    error: "signal 'top.ghost' not found in graph",
    error_code: "E_SIGNAL_NOT_FOUND",
  }],
};

/** Real `sv_query trace fanin` envelope for a relative name matching 2 nodes. */
const AMBIGUOUS_PAYLOAD = {
  ok: false,
  command: "trace_fanin",
  result: {
    signals: [{
      signal: "x",
      index: 0,
      drivers: [],
      count: 0,
      error: "signal 'x' is ambiguous (2 matches); use a longer path or one of: top.u_sub.x, top.u_sub2.x",
      resolved_signal: null,
      resolution: "ambiguous",
      candidates: ["top.u_sub.x", "top.u_sub2.x"],
      suggestions: [],
      top_ambiguous: false,
    }],
    total_signals: 1,
    failed_signals: 1,
  },
  errors: [{
    signal: "x",
    index: 0,
    error: "signal 'x' is ambiguous (2 matches); use a longer path or one of: top.u_sub.x, top.u_sub2.x",
    error_code: "E_SIGNAL_AMBIGUOUS",
  }],
};

/**
 * The `fail()` envelope emitted by `sv_query paths` when an endpoint is not
 * in the graph. It has a top-level `error` but no `result`, no `errors[]`
 * array, and no `error_code`.
 */
const FAIL_ENVELOPE = {
  ok: false,
  error: "signal id not found in graph",
  unknown: ["top.ghost"],
  hint: "use `svq graph nodes --json` to list available ids",
};

function thrown(message = "boom", code = undefined) {
  const err = new Error(message);
  if (code !== undefined) err.code = code;
  return err;
}

/** Collect the paths of every `undefined` value in a nested object. */
function undefinedPaths(value, path = "", out = []) {
  for (const [key, child] of Object.entries(value)) {
    const here = path ? `${path}.${key}` : key;
    if (child === undefined) out.push(here);
    else if (child && typeof child === "object" && !Array.isArray(child)) {
      undefinedPaths(child, here, out);
    }
  }
  return out;
}

test("not_found: a missing signal reports status not_found", () => {
  const out = failureResult(ARGS, thrown("boom"), NOT_FOUND_PAYLOAD);

  assert.equal(out.ok, false);
  assert.equal(out.status, "not_found");
  assert.equal(out.found, false);
  assert.equal(out.error.code, "E_SIGNAL_NOT_FOUND");
  assert.equal(out.error.message, "signal 'top.ghost' not found in graph");
  assert.deepEqual(out.error.candidates, []);
  assert.deepEqual(out.error.suggestions, ["top.ghost_int"]);
});

test("not_found: the row resolution alone is enough to classify", () => {
  // A payload whose `errors[]` entry is missing still classifies, because the
  // row carries `resolution: "not_found"`.
  const { errors, ...withoutErrors } = NOT_FOUND_PAYLOAD;
  const out = failureResult(ARGS, thrown("boom"), withoutErrors);
  assert.equal(out.status, "not_found");
  assert.equal(out.error.code, "E_QUERY_FAILED");
});

test("ambiguous: multiple candidates report status ambiguous", () => {
  const out = failureResult(ARGS, thrown("boom"), AMBIGUOUS_PAYLOAD);

  assert.equal(out.ok, false);
  assert.equal(out.status, "ambiguous");
  assert.equal(out.found, false);
  assert.equal(out.error.code, "E_SIGNAL_AMBIGUOUS");
  assert.deepEqual(out.error.candidates, ["top.u_sub.x", "top.u_sub2.x"]);
  assert.deepEqual(out.error.suggestions, []);
});

test("ambiguous: the E_SIGNAL_AMBIGUOUS code alone classifies as ambiguous", () => {
  // `sv_query trace` always pairs the code with `resolution: "ambiguous"`,
  // but the stable code is sufficient on its own: an envelope that carries
  // only `errors[].error_code` must still be classified, not degraded to a
  // generic error.
  const payload = {
    ok: false,
    errors: [{ error: "signal 'x' is ambiguous (2 matches)", error_code: "E_SIGNAL_AMBIGUOUS" }],
  };
  const out = failureResult(ARGS, thrown("boom"), payload);
  assert.equal(out.status, "ambiguous");
  assert.equal(out.found, false);
  assert.equal(out.error.code, "E_SIGNAL_AMBIGUOUS");
});

test("ambiguous: classifyFailure maps E_SIGNAL_AMBIGUOUS without a resolution", () => {
  assert.deepEqual(
    classifyFailure({ errors: [{ error_code: "E_SIGNAL_AMBIGUOUS" }] }),
    { status: "ambiguous", code: "E_SIGNAL_AMBIGUOUS" },
  );
});

test("ambiguous: top_ambiguous alone classifies as ambiguous", () => {
  // Multiple top modules in the snapshot: the query itself succeeds, but a
  // failure raised alongside it still reports the ambiguity.
  const payload = {
    ok: false,
    result: {
      signals: [{ signal: "x", error: "boom", resolution: "exact", top_ambiguous: true }],
    },
    errors: [{ error: "boom" }],
  };
  const out = failureResult(ARGS, thrown("boom"), payload);
  assert.equal(out.status, "ambiguous");
});

test("generic error: an unclassifiable failure reports status error", () => {
  const out = failureResult(ARGS, thrown("spawn failed", "ENOENT"), FAIL_ENVELOPE);

  assert.equal(out.ok, false);
  assert.equal(out.status, "error");
  assert.equal(out.found, false);
  assert.equal(out.error.code, "ENOENT");
  assert.equal(out.error.message, "spawn failed");
  assert.deepEqual(out.error.candidates, []);
  assert.deepEqual(out.error.suggestions, []);
});

test("generic error: a failure with no code falls back to E_QUERY_FAILED", () => {
  const out = failureResult(ARGS, thrown("boom"), { ok: false, error: "nope" });
  assert.equal(out.error.code, "E_QUERY_FAILED");
  assert.equal(out.status, "error");
});

test("generic error: a numeric error code never reaches error.code", () => {
  // Node sets `err.code` to the child's exit status when a command fails
  // non-zero, so `1` used to be reported as the error code. The contract
  // requires a stable `E_*` string.
  const out = failureResult(ARGS, thrown("Command failed: sv_query paths ...", 1), FAIL_ENVELOPE);
  assert.equal(out.error.code, "E_QUERY_FAILED");
  assert.equal(typeof out.error.code, "string");
  assert.equal(out.status, "error");
});

test("generic error: a non-string error code never reaches error.code", () => {
  for (const code of [1, 0, 42, true, {}, [], Symbol("x")]) {
    const out = failureResult(ARGS, thrown("boom", code), FAIL_ENVELOPE);
    assert.equal(out.error.code, "E_QUERY_FAILED");
    assert.equal(typeof out.error.code, "string");
  }
});

test("generic error: failureCode rejects non-string codes", () => {
  assert.equal(failureCode(undefined, thrown("boom", 1)), "E_QUERY_FAILED");
  assert.equal(failureCode(undefined, thrown("boom", "ENOENT")), "ENOENT");
  assert.equal(failureCode(undefined, thrown("boom", "")), "E_QUERY_FAILED");
  assert.equal(failureCode(NOT_FOUND_PAYLOAD, thrown("boom", 1)), "E_SIGNAL_NOT_FOUND");
});

test("generic error: classifyFailure keeps the code a stable string", () => {
  const { code } = classifyFailure(undefined, 1);
  assert.equal(code, "E_QUERY_FAILED");
  assert.equal(typeof code, "string");
});

test("generic error: no payload at all still yields a well-formed envelope", () => {
  const out = failureResult(ARGS, thrown("boom"));
  assert.equal(out.ok, false);
  assert.equal(out.status, "error");
  assert.equal(out.found, false);
  assert.equal(out.error.code, "E_QUERY_FAILED");
  assert.equal(out.error.message, "boom");
});

test("failure envelope echoes the request context", () => {
  const out = failureResult(
    { intent: "path", snapshot: "s", signal: "a", dst: "b" },
    thrown("boom"),
    NOT_FOUND_PAYLOAD,
  );
  assert.equal(out.intent, "path");
  assert.equal(out.snapshot, "s");
  assert.equal(out.signal, "a");
  assert.equal(out.dst, "b");
});

test("failure envelope uses null for absent signal and dst", () => {
  const out = failureResult({ intent: "evidence", snapshot: "s" }, thrown("boom"));
  assert.equal(out.signal, null);
  assert.equal(out.dst, null);
});

test("failure envelope carries no undefined fields and round-trips as JSON", () => {
  const payloads = [NOT_FOUND_PAYLOAD, AMBIGUOUS_PAYLOAD, FAIL_ENVELOPE, undefined];
  for (const payload of payloads) {
    const out = failureResult(ARGS, thrown("boom"), payload);
    assert.deepEqual(undefinedPaths(out), []);
    const text = JSON.stringify(out);
    assert.deepEqual(JSON.parse(text), out);
    // Round-tripping the parsed form yields the identical serialized text.
    assert.equal(JSON.stringify(JSON.parse(text)), text);
  }
});

test("failure envelope always reports evidence_available false", () => {
  const out = failureResult(ARGS, thrown("boom"), NOT_FOUND_PAYLOAD);
  assert.equal(out.evidence_available, false);
});

test("the injected payload overrides the payload attached to the error", () => {
  const err = thrown("boom");
  err.payload = FAIL_ENVELOPE;
  const out = failureResult(ARGS, err, NOT_FOUND_PAYLOAD);
  assert.equal(out.status, "not_found");
  assert.equal(out.error.code, "E_SIGNAL_NOT_FOUND");
});

test("the payload attached to the error is used when none is injected", () => {
  const err = thrown("boom");
  err.payload = NOT_FOUND_PAYLOAD;
  const out = failureResult(ARGS, err);
  assert.equal(out.status, "not_found");
  assert.equal(out.error.code, "E_SIGNAL_NOT_FOUND");
});

test("classifyFailure is pure and reports status plus code", () => {
  assert.deepEqual(classifyFailure(NOT_FOUND_PAYLOAD), {
    status: "not_found", code: "E_SIGNAL_NOT_FOUND",
  });
  assert.deepEqual(classifyFailure(AMBIGUOUS_PAYLOAD), {
    status: "ambiguous", code: "E_SIGNAL_AMBIGUOUS",
  });
  assert.deepEqual(classifyFailure(FAIL_ENVELOPE), {
    status: "error", code: "E_QUERY_FAILED",
  });
  assert.deepEqual(classifyFailure(undefined), {
    status: "error", code: "E_QUERY_FAILED",
  });
});

test("classifyFailure reports a status from the allowed set", () => {
  const payloads = [NOT_FOUND_PAYLOAD, AMBIGUOUS_PAYLOAD, FAIL_ENVELOPE, {}, null, 42, "x"];
  for (const payload of payloads) {
    assert.ok(FAILURE_STATUSES.includes(classifyFailure(payload).status));
  }
});

test("failureParts locates the row and the first error entry", () => {
  const { row, first } = failureParts(NOT_FOUND_PAYLOAD);
  assert.equal(row.resolution, "not_found");
  assert.equal(first.error_code, "E_SIGNAL_NOT_FOUND");
});

test("failureParts tolerates malformed payloads", () => {
  for (const payload of [undefined, null, 42, "x", [], { result: 1 }, { errors: 1 }]) {
    assert.deepEqual(failureParts(payload), { row: {}, first: {} });
  }
});

test("failureCode prefers the payload code over the error code", () => {
  assert.equal(failureCode(NOT_FOUND_PAYLOAD, thrown("boom", "ENOENT")), "E_SIGNAL_NOT_FOUND");
  assert.equal(failureCode(undefined, thrown("boom", "ENOENT")), "ENOENT");
  assert.equal(failureCode(undefined, thrown("boom")), "E_QUERY_FAILED");
});

test("failureDetail reports message, candidates, and suggestions", () => {
  const detail = failureDetail(NOT_FOUND_PAYLOAD, thrown("boom"));
  assert.equal(detail.message, "signal 'top.ghost' not found in graph");
  assert.deepEqual(detail.candidates, []);
  assert.deepEqual(detail.suggestions, ["top.ghost_int"]);
});

test("failureDetail falls back to the thrown message", () => {
  const detail = failureDetail(undefined, thrown("boom"));
  assert.equal(detail.message, "boom");
});
