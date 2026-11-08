/**
 * Pure bounded fanin BFS for the `neighborhood` intent.
 *
 * No I/O and no runtime imports beyond the pure compaction helper: the caller
 * injects `queryFn(args)`, which must return one raw `sv_query --json` payload.
 * `index.js` supplies the real child-process-backed query function.
 */

import { conditionAtoms } from "./compact.js";

/**
 * Walk fanin (drivers only) breadth-first from `signal`.
 *
 * @param {(args: string[]) => Promise<object>} queryFn
 *   Called once per expanded node with
 *   `["drivers", id, "--depth", "1", "--from-snapshot", snapshot, "--json"]`.
 * @param {object} options
 * @param {string} options.signal  Seed signal id.
 * @param {string} options.snapshot  Prebuilt snapshot tag.
 * @param {number} options.maxDepth  Number of BFS levels to expand (1..8).
 * @param {number} [options.maxNodes=100]  Soft node budget.
 * @returns {Promise<object>} The unchanged neighborhood result schema.
 *
 * Malformed driver rows (rows whose `id` is not a string) are ignored rather
 * than failing the whole walk. This preserves the tool's historical behavior
 * and lets one bad row coexist with valid fanin data.
 *
 * The node budget is checked before each frontier node is expanded, not after
 * every discovered row. A single query can therefore push the final node count
 * past `maxNodes`; `truncated` only means expansion stopped early.
 */
export async function neighborhood(queryFn, {
  signal,
  snapshot,
  maxDepth,
  maxNodes = 100,
}) {
  const base = ["--from-snapshot", snapshot, "--json"];
  const nodes = new Map();
  const edges = [];
  const seenEdges = new Set();
  let truncated = false;
  let frontier = [{ id: signal, depth: 0, kind: null }];
  nodes.set(signal, { id: signal, kind: null, depth: 0 });
  for (let level = 0; level < maxDepth; level++) {
    const next = [];
    for (const item of frontier) {
      if (nodes.size > maxNodes) { truncated = true; break; }
      const d = await queryFn(["drivers", item.id, "--depth", "1", ...base]);
      const rows = d.result?.signals?.[0]?.drivers || [];
      for (const row of rows) {
        const id = row.id;
        if (typeof id !== "string") continue;
        if (!nodes.has(id)) {
          nodes.set(id, { id, kind: row.kind ?? null, depth: level + 1 });
          next.push({ id, depth: level + 1, kind: row.kind ?? null });
        }
        const key = `${id}\u0000${item.id}\u0000${row.condition || ""}`;
        if (!seenEdges.has(key)) {
          seenEdges.add(key);
          edges.push({
            src: id, dst: item.id,
            kind: row.kind ?? null,
            condition: row.condition ?? "",
          });
        }
      }
    }
    if (truncated || next.length === 0) break;
    frontier = next;
  }
  const nodeList = [...nodes.values()];
  const opTernary = nodeList.filter((n) => n.kind === "OP_TERNARY").map((n) => n.id);
  const conditions = [...new Set(edges.map((e) => e.condition).filter(Boolean))];
  return {
    ok: true, intent: "neighborhood", snapshot,
    signal, depth: maxDepth,
    nodes: nodeList, edges,
    op_ternary: opTernary,
    conditions,
    condition_atoms: conditionAtoms(conditions),
    count: nodeList.length, truncated,
  };
}
