import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { defineTool } from "@deepseek-ai/dsh-tools";

const execFileP = promisify(execFile);

export const name = "svq-query-tool";
export const inject = ["tools"];

const INTENTS = ["fanin", "fanout", "neighbors", "path"];

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

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: "svq_query",
    description:
      "Query canonical RTL graph facts from a prebuilt snapshot. Use this " +
      "instead of shell commands. Supports direct fanin/fanout and structural paths.",
    parameters: {
      intent: {
        type: "string", required: true, enum: INTENTS,
        description: "fanin (drivers), fanout (loads), neighbors (both), or path (src -> dst).",
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
        throw new Error("intent must be fanin, fanout, or path");
      }
      if (!/^[A-Za-z0-9_.-]+$/.test(args.snapshot)) {
        throw new Error("invalid snapshot tag");
      }
      const base = ["--from-snapshot", args.snapshot, "--json"];
      const depth = args.depth ?? 1;
      if (args.intent === "path") {
        if (!args.dst) throw new Error("path requires dst");
        const d = await query(["paths", args.signal, args.dst, "--directed", ...base]);
        return {
          ok: d.ok !== false,
          intent: "path", snapshot: args.snapshot,
          path: d.path || [], count: d.hop_count ?? null,
        };
      }
      if (depth < 1 || depth > 32) throw new Error("depth must be 1..32");
      const run = async (cmd) => {
        const d = await query([cmd, args.signal, "--depth", String(depth), ...base]);
        const s = d.result?.signals?.[0] || {};
        return (cmd === "drivers" ? s.drivers : s.loads) || [];
      };
      if (args.intent === "neighbors") {
        const drivers = await run("drivers");
        const loads = await run("loads");
        return {
          ok: true, intent: "neighbors", snapshot: args.snapshot,
          signal: args.signal,
          drivers: drivers.map((x) => x.id),
          loads: loads.map((x) => x.id),
          count: drivers.length + loads.length,
        };
      }
      const rows = await run(args.intent === "fanin" ? "drivers" : "loads");
      const ids = rows.map((x) => x.id);
      return {
        ok: true, intent: args.intent, snapshot: args.snapshot,
        signal: args.signal,
        [args.intent === "fanin" ? "drivers" : "loads"]: ids,
        count: ids.length,
      };
    },
  }));
}
