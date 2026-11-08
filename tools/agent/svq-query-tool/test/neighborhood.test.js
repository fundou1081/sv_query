import test from "node:test";
import assert from "node:assert/strict";

import { neighborhood } from "../neighborhood.js";

const SNAPSHOT = "test_snap";

/** Build a fake queryFn over a `{ signal: driverRows[] }` graph. */
function makeQuery(graph, calls = []) {
  return async (args) => {
    calls.push(args);
    const id = args[1];
    const rows = graph[id] ?? [];
    return { ok: true, result: { signals: [{ signal: id, drivers: rows }] } };
  };
}

function driver(id, kind = "SIGNAL", condition = "") {
  return { id, kind, condition };
}

function ids(nodes) {
  return nodes.map((n) => n.id);
}

test("stops at maxDepth and does not expand the deepest frontier", async () => {
  const graph = {
    root: [driver("a")],
    a: [driver("b")],
    b: [driver("c")],
  };
  const calls = [];
  const out = await neighborhood(makeQuery(graph, calls), {
    signal: "root", snapshot: SNAPSHOT, maxDepth: 2, maxNodes: 100,
  });

  assert.deepEqual(ids(out.nodes), ["root", "a", "b"]);
  assert.deepEqual(out.nodes.map((n) => n.depth), [0, 1, 2]);
  assert.equal(out.count, 3);
  assert.equal(out.truncated, false);
  assert.deepEqual(out.edges.map((e) => [e.src, e.dst]), [["a", "root"], ["b", "a"]]);
  // "b" is at the depth cutoff, so its drivers must never be queried.
  assert.deepEqual(calls.map((c) => c[1]), ["root", "a"]);
});

test("calls the injected query with snapshot-scoped drivers args", async () => {
  const calls = [];
  await neighborhood(makeQuery({ root: [] }, calls), {
    signal: "root", snapshot: SNAPSHOT, maxDepth: 1, maxNodes: 100,
  });

  assert.deepEqual(calls, [
    ["drivers", "root", "--depth", "1", "--from-snapshot", SNAPSHOT, "--json"],
  ]);
});

test("dedupes duplicate nodes and identical edges", async () => {
  const graph = {
    root: [driver("a"), driver("a")],
    a: [driver("shared"), driver("shared")],
  };
  const out = await neighborhood(makeQuery(graph), {
    signal: "root", snapshot: SNAPSHOT, maxDepth: 3, maxNodes: 100,
  });

  assert.deepEqual(ids(out.nodes), ["root", "a", "shared"]);
  assert.equal(out.count, 3);
  assert.deepEqual(
    out.edges.map((e) => `${e.src}->${e.dst}:${e.condition}`),
    ["a->root:", "shared->a:"],
  );
});

test("collects branch conditions and normalizes condition atoms", async () => {
  const graph = {
    root: [
      driver("a", "SIGNAL", "sel[0]"),
      driver("b", "SIGNAL", "!(sel[0])"),
      driver("c", "SIGNAL", "sel[1]"),
      driver("d", "SIGNAL", "sel[1]"),
      driver("e", "SIGNAL", "(mode == 0)"),
      driver("f", "SIGNAL", ""),
    ],
  };
  const out = await neighborhood(makeQuery(graph), {
    signal: "root", snapshot: SNAPSHOT, maxDepth: 1, maxNodes: 100,
  });

  assert.deepEqual(out.conditions, [
    "sel[0]", "!(sel[0])", "sel[1]", "(mode == 0)",
  ]);
  assert.deepEqual(out.condition_atoms, ["sel[0]", "sel[1]", "mode == 0"]);
});

test("extracts OP_TERNARY node ids", async () => {
  const graph = {
    root: [
      driver("mux0", "OP_TERNARY", "sel[0]"),
      driver("mux1", "OP_TERNARY", "sel[1]"),
      driver("plain", "SIGNAL"),
    ],
  };
  const out = await neighborhood(makeQuery(graph), {
    signal: "root", snapshot: SNAPSHOT, maxDepth: 1, maxNodes: 100,
  });

  assert.deepEqual(out.op_ternary, ["mux0", "mux1"]);
  assert.deepEqual(
    out.nodes.map((n) => n.kind),
    [null, "OP_TERNARY", "OP_TERNARY", "SIGNAL"],
  );
});

test("sets truncated when the node budget is exceeded", async () => {
  const graph = {
    root: ["a", "b", "c", "d", "e"].map((id) => driver(id)),
    a: [driver("deep")],
  };
  const calls = [];
  const out = await neighborhood(makeQuery(graph, calls), {
    signal: "root", snapshot: SNAPSHOT, maxDepth: 8, maxNodes: 2,
  });

  assert.equal(out.truncated, true);
  assert.equal(out.depth, 8);
  // The root query fills the frontier; the next expansion notices the budget.
  assert.equal(calls.length, 1);
  assert.deepEqual(calls.map((c) => c[1]), ["root"]);
  assert.deepEqual(ids(out.nodes), ["root", "a", "b", "c", "d", "e"]);
});

test("ignores malformed driver rows with non-string ids", async () => {
  const graph = {
    root: [
      { kind: "SIGNAL" },
      { id: 42, kind: "SIGNAL" },
      { id: null, kind: "SIGNAL" },
      driver("kept", "SIGNAL", "sel"),
    ],
  };
  const out = await neighborhood(makeQuery(graph), {
    signal: "root", snapshot: SNAPSHOT, maxDepth: 1, maxNodes: 100,
  });

  assert.deepEqual(ids(out.nodes), ["root", "kept"]);
  assert.equal(out.edges.length, 1);
  assert.deepEqual(out.conditions, ["sel"]);
});
