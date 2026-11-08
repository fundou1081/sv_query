import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, isAbsolute, resolve } from "node:path";
import { promisify } from "node:util";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { INTENTS, compactResult } from "./compact.js";
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

function resolveSourceFile(file) {
  if (!file) return null;
  if (isAbsolute(file)) return existsSync(file) ? file : null;
  const root = process.env.SVQ_SOURCE_ROOT;
  if (!root) return null;
  const p = resolve(root, file);
  return existsSync(p) ? p : null;
}

/** Add bounded file/line/source_line evidence for returned node ids only. */
async function collectEvidence(snapshot, ids) {
  const snap = await readSnapshot(snapshot);
  if (!snap) return null;
  const byId = new Map((snap.nodes || []).map((n) => [n.id, n]));
  const lines = new Map();
  const evidence = {};
  for (const id of [...new Set(ids)].slice(0, 80)) {
    const node = byId.get(id);
    if (!node) continue;
    const rec = { file: node.file || null, line: node.line || null };
    const source = resolveSourceFile(node.file);
    if (source && Number.isInteger(node.line) && node.line > 0) {
      try {
        let content = lines.get(source);
        if (!content) {
          content = (await readFile(source, "utf8")).split(/\r?\n/);
          lines.set(source, content);
        }
        const text = (content[node.line - 1] || "").trim();
        if (text) rec.source_line = text.slice(0, 160);
        const startLine = Math.max(1, node.line - 2);
        const endLine = Math.min(content.length, node.line + 2);
        rec.source_context = [];
        for (let n = startLine; n <= endLine; n++) {
          const line = (content[n - 1] || "").trim();
          if (line) rec.source_context.push({ line: n, text: line.slice(0, 160) });
        }
      } catch {
        rec.source_missing = true;
      }
    }
    evidence[id] = rec;
  }
  return evidence;
}

async function addEvidence(out, args) {
  if (!args.evidence) return out;
  const wanted = [];
  for (const key of ["drivers", "loads", "path"]) {
    for (const id of out[key] || []) if (typeof id === "string") wanted.push(id);
  }
  for (const n of out.nodes || []) if (n && typeof n.id === "string") wanted.push(n.id);
  const evidence = await collectEvidence(args.snapshot, wanted);
  if (!evidence) return { ...out, evidence_error: "snapshot metadata unavailable" };
  return { ...out, evidence };
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
        description: "fanin, fanout, neighbors, path, neighborhood (bounded fanin BFS), or evidence (source file/line context for one node).",
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
    },
    output: {
      schema: { type: "object", additionalProperties: true },
      render: (_args, value) => [{
        type: "text",
        text: JSON.stringify(value, null, 2),
      }],
    },
    async execute(args) {
      if (!INTENTS.includes(args.intent)) {
        throw new Error(`intent must be one of: ${INTENTS.join(", ")}`);
      }
      if (!/^[A-Za-z0-9_.-]+$/.test(args.snapshot)) {
        throw new Error("invalid snapshot tag");
      }
      if (args.intent === "evidence") {
        if (!args.signal) throw new Error("evidence requires signal");
        const rec = await collectEvidence(args.snapshot, [args.signal]);
        return { ok: true, intent: "evidence", snapshot: args.snapshot,
                 signal: args.signal, evidence: rec };
      }
      const base = ["--from-snapshot", args.snapshot, "--json"];
      const depth = args.depth ?? 1;
      const meta = { snapshot: args.snapshot, signal: args.signal,
                     details: args.details === true };
      if (args.intent === "path") {
        if (!args.dst) throw new Error("path requires dst");
        const payload = await query(["paths", args.signal, args.dst, "--all", "--max", "20",
                                     "--directed", ...base]);
        return await addEvidence(compactResult("path", payload, meta), args, payload);
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
    },
  }));
}
