import test from "node:test";
import assert from "node:assert/strict";

import { addEvidence, collectEvidence } from "../evidence.js";

const SOURCE_ROOT = "/fake/root";

function fileFromPath(path) {
  return path.slice(SOURCE_ROOT.length + 1);
}

/** Build fake snapshot/source dependencies backed by in-memory maps. */
function fakeDeps({ nodes, sources = {}, unreadable = [] }) {
  const unreadableFiles = new Set(unreadable);
  return {
    readSnapshot: async () => ({ nodes }),
    resolveSource: (file, sourceRoot) => {
      if (!file) return null;
      const known = Object.hasOwn(sources, file) || unreadableFiles.has(file);
      if (!known) return null;
      return `${sourceRoot ?? SOURCE_ROOT}/${file}`;
    },
    readSource: async (path) => {
      const file = fileFromPath(path);
      if (unreadableFiles.has(file)) throw new Error(`cannot read ${file}`);
      return sources[file];
    },
    sourceRoot: SOURCE_ROOT,
  };
}

test("includes +/-2 lines of trimmed context around the node line", async () => {
  const deps = fakeDeps({
    nodes: [{ id: "top.a", file: "top.sv", line: 4 }],
    sources: {
      "top.sv": [
        "module top;", // 1
        "", // 2 blank, skipped
        "  assign a = b;", // 3
        "  assign c = d;", // 4 target
        "  assign e = f;", // 5
        "endmodule", // 6
        "tail", // 7 outside the window
      ].join("\n"),
    },
  });

  const out = await collectEvidence({
    ...deps, snapshot: "ad_axi", ids: ["top.a"],
  });

  assert.deepEqual(out, {
    "top.a": {
      file: "top.sv",
      line: 4,
      source_line: "assign c = d;",
      source_context: [
        { line: 3, text: "assign a = b;" },
        { line: 4, text: "assign c = d;" },
        { line: 5, text: "assign e = f;" },
        { line: 6, text: "endmodule" },
      ],
    },
  });
});

test("clamps the context window at the first and last source line", async () => {
  const deps = fakeDeps({
    nodes: [
      { id: "top.first", file: "top.sv", line: 1 },
      { id: "top.last", file: "top.sv", line: 5 },
    ],
    sources: { "top.sv": "one\ntwo\nthree\nfour\nfive" },
  });

  const out = await collectEvidence({
    ...deps, snapshot: "s", ids: ["top.first", "top.last"],
  });

  assert.deepEqual(out["top.first"].source_context.map((x) => x.line), [1, 2, 3]);
  assert.deepEqual(out["top.last"].source_context.map((x) => x.line), [3, 4, 5]);
});

test("source_line evidence is the trimmed text of the node line", async () => {
  const deps = fakeDeps({
    nodes: [{ id: "top.a", file: "top.sv", line: 2 }],
    sources: { "top.sv": "header\n   wire foo;   \nfooter" },
  });

  const out = await collectEvidence({ ...deps, snapshot: "s", ids: ["top.a"] });

  assert.equal(out["top.a"].file, "top.sv");
  assert.equal(out["top.a"].line, 2);
  assert.equal(out["top.a"].source_line, "wire foo;");
});

test("skips requested ids that are missing from the snapshot", async () => {
  const deps = fakeDeps({
    nodes: [
      { id: "top.a", file: "top.sv", line: 1 },
      { id: "top.not_requested", file: "top.sv", line: 2 },
    ],
    sources: { "top.sv": "one\ntwo" },
  });

  const out = await collectEvidence({
    ...deps, snapshot: "s", ids: ["top.a", "top.ghost"],
  });

  assert.deepEqual(Object.keys(out), ["top.a"]);
  assert.equal(out["top.ghost"], undefined);
  assert.equal(out["top.not_requested"], undefined);
});

test("keeps file/line but omits source fields when the file is missing", async () => {
  const deps = fakeDeps({
    nodes: [
      { id: "top.a", file: "absent.sv", line: 3 },
      { id: "top.nofile", line: null },
    ],
    sources: {},
  });

  const out = await collectEvidence({
    ...deps, snapshot: "s", ids: ["top.a", "top.nofile"],
  });

  assert.deepEqual(out["top.a"], { file: "absent.sv", line: 3 });
  assert.deepEqual(out["top.nofile"], { file: null, line: null });
});

test("marks source_missing when a resolved source cannot be read", async () => {
  const deps = fakeDeps({
    nodes: [{ id: "top.a", file: "secret.sv", line: 2 }],
    sources: {},
    unreadable: ["secret.sv"],
  });

  const out = await collectEvidence({ ...deps, snapshot: "s", ids: ["top.a"] });

  assert.deepEqual(out["top.a"], {
    file: "secret.sv",
    line: 2,
    source_missing: true,
  });
});

test("caps source_line and context text at 160 characters", async () => {
  const long = "x".repeat(200);
  const deps = fakeDeps({
    nodes: [{ id: "top.long", file: "long.sv", line: 1 }],
    sources: { "long.sv": `  ${long}\nshort` },
  });

  const out = await collectEvidence({ ...deps, snapshot: "s", ids: ["top.long"] });

  assert.equal(out["top.long"].source_line, "x".repeat(160));
  assert.equal(out["top.long"].source_line.length, 160);
  assert.equal(out["top.long"].source_context[0].text, "x".repeat(160));
  assert.equal(out["top.long"].source_context[0].text.length, 160);
});

test("emits at most 80 evidence records", async () => {
  const nodes = Array.from({ length: 100 }, (_, i) => ({
    id: `top.n${i}`, file: "top.sv", line: 1,
  }));
  const deps = fakeDeps({
    nodes,
    sources: { "top.sv": "one\ntwo\nthree" },
  });

  const out = await collectEvidence({
    ...deps, snapshot: "s", ids: nodes.map((n) => n.id),
  });

  assert.equal(Object.keys(out).length, 80);
  assert.ok(out["top.n0"]);
  assert.ok(out["top.n79"]);
  assert.equal(out["top.n80"], undefined);
});

test("deduplicates ids before applying the 80-record cap", async () => {
  const nodes = [{ id: "top.only", file: "top.sv", line: 1 }];
  const deps = fakeDeps({
    nodes,
    sources: { "top.sv": "one\ntwo\nthree" },
  });

  const out = await collectEvidence({
    ...deps, snapshot: "s", ids: Array(100).fill("top.only"),
  });

  assert.deepEqual(Object.keys(out), ["top.only"]);
});

test("passes sourceRoot through to resolveSource", async () => {
  const seen = [];
  const out = await collectEvidence({
    snapshot: "s",
    ids: ["top.a"],
    readSnapshot: async () => ({ nodes: [{ id: "top.a", file: "top.sv", line: 1 }] }),
    resolveSource: (file, sourceRoot) => {
      seen.push([file, sourceRoot]);
      return null;
    },
    readSource: async () => {
      throw new Error("readSource must not run when the source is unresolved");
    },
    sourceRoot: "/custom/root",
  });

  assert.deepEqual(seen, [["top.sv", "/custom/root"]]);
  assert.deepEqual(out["top.a"], { file: "top.sv", line: 1 });
});

test("leaves the result untouched when evidence is not requested", async () => {
  const out = { ok: true, drivers: ["top.a"] };
  const result = await addEvidence(out, { evidence: false, snapshot: "s" }, {});

  assert.equal(result, out);
});

test("adds evidence for drivers, loads, path, and nodes", async () => {
  const deps = fakeDeps({
    nodes: ["top.d", "top.l", "top.p", "top.n"].map((id) => ({
      id, file: "top.sv", line: 1,
    })),
    sources: { "top.sv": "one\ntwo\nthree" },
  });
  const out = {
    ok: true,
    drivers: ["top.d"],
    loads: ["top.l"],
    path: ["top.p"],
    nodes: [{ id: "top.n" }],
  };

  const result = await addEvidence(
    out,
    { evidence: true, snapshot: "s" },
    deps,
  );

  assert.deepEqual(Object.keys(result.evidence), [
    "top.d", "top.l", "top.p", "top.n",
  ]);
  assert.deepEqual(result.drivers, ["top.d"]);
});

test("reports evidence_error when snapshot metadata is unavailable", async () => {
  const deps = { ...fakeDeps({ nodes: [] }), readSnapshot: async () => null };

  const result = await addEvidence(
    { ok: true, drivers: ["top.a"] },
    { evidence: true, snapshot: "missing" },
    deps,
  );

  assert.deepEqual(result, {
    ok: true,
    drivers: ["top.a"],
    evidence_error: "snapshot metadata unavailable",
  });
});
