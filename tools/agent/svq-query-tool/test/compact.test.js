import test from "node:test";
import assert from "node:assert/strict";

import {
  compactFanin,
  compactFanout,
  compactNeighbors,
  compactPath,
  compactResult,
} from "../compact.js";

const meta = { snapshot: "ad_axi", signal: "top.u_axi.araddr" };

function signalPayload(field, rows) {
  return { ok: true, result: { signals: [{ signal: meta.signal, [field]: rows }] } };
}

function nodes(...ids) {
  return ids.map((id) => ({ id, kind: "signal", module: "top" }));
}

test("fanin compacts driver ids", () => {
  const out = compactFanin(signalPayload("drivers", nodes("top.a", "top.b")), meta);
  assert.deepEqual(out, {
    ok: true,
    intent: "fanin",
    snapshot: "ad_axi",
    signal: "top.u_axi.araddr",
    drivers: ["top.a", "top.b"],
    count: 2,
  });
});

test("fanout compacts load ids", () => {
  const out = compactFanout(signalPayload("loads", nodes("top.c")), meta);
  assert.deepEqual(out, {
    ok: true,
    intent: "fanout",
    snapshot: "ad_axi",
    signal: "top.u_axi.araddr",
    loads: ["top.c"],
    count: 1,
  });
});

test("neighbors combines drivers and loads", () => {
  const out = compactNeighbors(
    signalPayload("drivers", nodes("top.a")),
    signalPayload("loads", nodes("top.b", "top.c")),
    meta,
  );
  assert.deepEqual(out, {
    ok: true,
    intent: "neighbors",
    snapshot: "ad_axi",
    signal: "top.u_axi.araddr",
    drivers: ["top.a"],
    loads: ["top.b", "top.c"],
    count: 3,
  });
});

test("path keeps canonical path and hop count", () => {
  const payload = {
    ok: true,
    found: true,
    hop_count: 2,
    path: ["top.a", "top.mid", "top.b"],
  };
  assert.deepEqual(compactPath(payload, meta), {
    ok: true,
    intent: "path",
    snapshot: "ad_axi",
    path: ["top.a", "top.mid", "top.b"],
    count: 2,
  });
});

test("path without a found path stays ok with empty path", () => {
  const payload = { ok: true, found: false, hop_count: null, path: null };
  assert.deepEqual(compactPath(payload, meta), {
    ok: true,
    intent: "path",
    snapshot: "ad_axi",
    path: [],
    count: null,
  });
});

test("empty signals payload yields an empty list", () => {
  const payload = { ok: true, result: { signals: [] } };
  assert.deepEqual(compactFanin(payload, meta), {
    ok: true,
    intent: "fanin",
    snapshot: "ad_axi",
    signal: "top.u_axi.araddr",
    drivers: [],
    count: 0,
  });
  assert.deepEqual(
    compactNeighbors(payload, payload, meta).count,
    0,
  );
});

test("empty driver/load arrays yield count zero", () => {
  const out = compactFanout(signalPayload("loads", []), meta);
  assert.deepEqual(out.loads, []);
  assert.equal(out.count, 0);
});

test("missing result object throws explicitly", () => {
  assert.throws(() => compactFanin({}, meta), /missing result object/);
  assert.throws(
    () => compactFanin({ ok: true, result: {} }, meta),
    /missing result\.signals array/,
  );
});

test("failure envelope throws explicitly", () => {
  assert.throws(
    () => compactFanin({ ok: false, error: "snapshot not found" }, meta),
    /returned failure: snapshot not found/,
  );
});

test("malformed node row throws instead of emitting undefined", () => {
  const payload = signalPayload("drivers", [{ kind: "signal" }]);
  assert.throws(() => compactFanin(payload, meta), /missing string id/);
});

test("malformed path payload throws explicitly", () => {
  assert.throws(
    () => compactPath({ ok: true, path: "top.a", hop_count: 0 }, meta),
    /path must be an array or null/,
  );
  assert.throws(
    () => compactPath({ ok: true, path: [], hop_count: "2" }, meta),
    /hop_count must be an integer or null/,
  );
});

test("compactResult dispatches all supported intents", () => {
  assert.equal(
    compactResult("fanin", signalPayload("drivers", nodes("top.a")), meta).count,
    1,
  );
  assert.equal(
    compactResult("fanout", signalPayload("loads", nodes("top.b")), meta).count,
    1,
  );
  assert.equal(
    compactResult("path", { ok: true, path: [], hop_count: 0 }, meta).count,
    0,
  );
  const neighbors = compactResult("neighbors", {
    drivers: signalPayload("drivers", nodes("top.a")),
    loads: signalPayload("loads", nodes("top.b")),
  }, meta);
  assert.equal(neighbors.count, 2);
  assert.throws(() => compactResult("impact", {}, meta), /unknown intent/);
});

test("fanin details carry kind, condition, distance", () => {
  const payload = signalPayload("drivers", [
    { id: "top.a", kind: "SIGNAL", condition: "sel[0]", distance: 1 },
  ]);
  const out = compactFanin(payload, { ...meta, details: true });
  assert.deepEqual(out.drivers, ["top.a"]);
  assert.deepEqual(out.driver_details, [
    { id: "top.a", kind: "SIGNAL", condition: "sel[0]", distance: 1 },
  ]);
});

test("neighbors details carry both sides", () => {
  const out = compactNeighbors(
    signalPayload("drivers", [{ id: "top.a", kind: "SIGNAL", condition: "sel" }]),
    signalPayload("loads", [{ id: "top.b", kind: "PORT_OUT" }]),
    { ...meta, details: true },
  );
  assert.equal(out.driver_details[0].condition, "sel");
  assert.deepEqual(out.load_details, [
    { id: "top.b", kind: "PORT_OUT", condition: "", distance: null },
  ]);
});

test("conditionAtoms strips polarity and duplicates", async () => {
  const { conditionAtoms } = await import("../compact.js");
  assert.deepEqual(
    conditionAtoms(["sel[0]", "!(sel[0])", "sel[1]", "!(sel[1])", ""]),
    ["sel[0]", "sel[1]"],
  );
  assert.deepEqual(conditionAtoms(["(mode == 0)"]), ["mode == 0"]);
});

test("path defaults to shortest, granular opts into longest", async () => {
  const { compactPath } = await import("../compact.js");
  const payload = {
    ok: true,
    all_paths: [
      ["a", "b"],
      ["a", "x", "b"],
      ["a", "c", "b"],
    ],
  };
  const short = compactPath(payload, { snapshot: "s" });
  assert.deepEqual(short.path, ["a", "b"]);
  assert.equal(short.count, 1);
  const long = compactPath(payload, { snapshot: "s", granular: true });
  assert.deepEqual(long.path, ["a", "c", "b"]);
  assert.equal(long.count, 2);
  assert.equal(long.variants, 3);
});
