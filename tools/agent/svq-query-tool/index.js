import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { existsSync, readdirSync, statSync } from "node:fs";
import { join, isAbsolute, resolve } from "node:path";
import { promisify } from "node:util";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { INTENTS, compactResult, compactVerify } from "./compact.js";
import {
  addEvidence as addEvidenceWith,
  collectEvidence as collectEvidenceWith,
  collectEdgeEvidence as collectEdgeEvidenceWith,
} from "./evidence.js";
import { failureResult } from "./failure.js";
import { neighborhood } from "./neighborhood.js";

const execFileP = promisify(execFile);

export const name = "svq-query-tool";
export const inject = ["tools"];

/** Run the installed sv_query binary without a shell. */
async function query(args) {
  const bin = process.env.SVQ_QUERY_BIN || "sv_query";
  const { stdout } = await execFileP(bin, args, {
    cwd: process.cwd(),
    env: process.env,
    timeout: 60000,
    maxBuffer: 8 * 1024 * 1024,
  });
  return JSON.parse(stdout);
}

async function readSnapshot(tag) {
  const dir = process.env.SVQ_SNAPSHOT_DIR;
  if (!dir) return null;
  const path = join(dir, `${tag}.json`);
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return null;
  }
}

function findSourceByName(root, basename, budget = 20000) {
  let seen = 0;
  const walk = (dir, depth) => {
    if (depth < 0 || seen > budget) return null;
    let entries;
    try {
      entries = readdirSync(dir);
    } catch {
      return null;
    }
    for (const name of entries) {
      seen += 1;
      if (seen > budget) return null;
      if (name === ".git" || name === "node_modules") continue;
      const p = resolve(dir, name);
      if (name === basename) {
        try {
          if (statSync(p).isFile()) return p;
        } catch {
          // ignore unreadable candidate
        }
      }
      try {
        if (statSync(p).isDirectory()) {
          const hit = walk(p, depth - 1);
          if (hit) return hit;
        }
      } catch {
        // ignore
      }
    }
    return null;
  };
  return walk(root, 8);
}

function resolveSourceFile(file, root) {
  if (!file) return null;
  if (isAbsolute(file)) return existsSync(file) ? file : null;
  if (!root) return null;
  const p = resolve(root, file);
  if (existsSync(p)) return p;
  // Snapshot source_locations often keep only the basename. Search inside the
  // configured source root as a bounded fallback; never escape the root.
  if (!file.includes("/") && !file.includes("\\")) {
    return findSourceByName(root, file);
  }
  return null;
}

function evidenceDeps() {
  return {
    readSnapshot,
    resolveSource: resolveSourceFile,
    readSource: (path) => readFile(path, "utf8"),
    sourceRoot: process.env.SVQ_SOURCE_ROOT,
  };
}

async function collectEvidence(snapshot, ids) {
  return collectEvidenceWith({ snapshot, ids, ...evidenceDeps() });
}

async function addEvidence(out, args) {
  return addEvidenceWith(out, args, evidenceDeps());
}

async function collectEdgeEvidence(snapshot, ids) {
  return collectEdgeEvidenceWith({ snapshot, ids, ...evidenceDeps() });
}

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: "svq_query",
    description:
      "Query canonical RTL graph facts from a prebuilt snapshot. Use this " +
      "instead of shell commands. Supports direct fanin/fanout and structural paths.",
    parameters: {
      intent: {
        type: "string", required: true, enum: INTENTS,
        description: "fanin, fanout, neighbors, path (canonical), deep_path (alias), neighborhood, evidence, or verify.",
      },
      snapshot: {
        type: "string", required: true,
        description: "Prebuilt snapshot tag, e.g. ad_axi.",
      },
      signal: {
        type: "string",
        description: "Canonical signal id for fanin/fanout.",
      },
      dst: {
        type: "string",
        description: "Destination signal id for path.",
      },
      depth: {
        type: "integer",
        description: "Hop depth; direct queries use 1.",
      },
      details: {
        type: "boolean",
        description: "Include kind/condition/distance for each neighbor.",
      },
      evidence: {
        type: "boolean",
        description: "Include file/line/source_line for returned node ids.",
      },
      claim: {
        type: "object",
        additionalProperties: true,
        description: "Verify intent only: claim object, e.g. {type:'driver',signal,dst?}.",
      },
      granular: {
        type: "boolean",
        description: "Deprecated; use intent=deep_path for the longest path variant.",
      },
    },
    output: {
      schema: { type: "object", additionalProperties: true },
      render: (_args, value) => [{
        type: "text",
        text: JSON.stringify(value, null, 2),
      }],
    },
    async execute(args) {
      try {
        return await executeInner(args);
      } catch (err) {
        return failureResult(args, err);
      }
    },
  }));
}

async function executeInner(args) {
      if (!INTENTS.includes(args.intent)) {
        throw new Error(`intent must be one of: ${INTENTS.join(", ")}`);
      }
      if (!/^[A-Za-z0-9_.-]+$/.test(args.snapshot)) {
        throw new Error("invalid snapshot tag");
      }
      if (args.intent === "verify") {
        if (!args.claim || typeof args.claim !== "object") {
          throw new Error("verify requires a claim object");
        }
        const payload = await query(["verify", "claim", "--from-snapshot",
                                     args.snapshot, "--claim",
                                     JSON.stringify(args.claim), "--json"]);
        return await addEvidence(compactVerify(payload, { snapshot: args.snapshot }), args);
      }
      if (args.intent === "evidence") {
        if (!args.signal) throw new Error("evidence requires signal");
        const rec = await collectEvidence(args.snapshot, [args.signal]);
        const edgeEvidence = await collectEdgeEvidence(args.snapshot, [args.signal]);
        if (!rec || !rec[args.signal]) {
          return { ok: false, status: "not_found", found: false,
                   intent: "evidence", snapshot: args.snapshot,
                   signal: args.signal, evidence: rec || {},
                   evidence_available: false,
                   error: { code: "E_EVIDENCE_NOT_FOUND",
                             message: "no evidence for signal" } };
        }
        return { ok: true, status: "ok", found: true,
                 intent: "evidence", snapshot: args.snapshot,
                 signal: args.signal, evidence_available: true,
                 evidence: rec, edge_evidence: edgeEvidence || [] };
      }
      const base = ["--from-snapshot", args.snapshot, "--json"];
      const depth = args.depth ?? 1;
      const meta = { snapshot: args.snapshot, signal: args.signal,
                     details: args.details === true };
      if (args.intent === "path" || args.intent === "deep_path") {
        if (!args.dst) throw new Error(`${args.intent} requires dst`);
        // Deterministic canonical path: max nodes, then lexicographic.
        // `deep_path` is kept as a compatibility alias; it no longer means
        // "some longest variant" without the canonical tie-break.
        const payload = await query(["paths", args.signal, args.dst,
                                     "--canonical", "--directed", ...base]);
        return await addEvidence(compactResult("path", payload,
                                               { ...meta, path_kind: "canonical" }),
                                 args, payload);
      }
      if (depth < 1 || depth > 32) throw new Error("depth must be 1..32");
      if (args.intent === "neighborhood") {
        if (depth > 8) throw new Error("neighborhood depth must be 1..8");
        return await neighborhood(query, {
          signal: args.signal,
          snapshot: args.snapshot,
          maxDepth: depth,
          maxNodes: 100,
        });
      }
      const fetch = (cmd) =>
        query([cmd, args.signal, "--depth", String(depth), ...base]);
      if (args.intent === "neighbors") {
        const [drivers, loads] = await Promise.all([
          fetch("drivers"),
          fetch("loads"),
        ]);
        return await addEvidence(compactResult("neighbors", { drivers, loads }, meta), args);
      }
      const payload = await fetch(args.intent === "fanin" ? "drivers" : "loads");
      return await addEvidence(compactResult(args.intent, payload, meta), args);
}
