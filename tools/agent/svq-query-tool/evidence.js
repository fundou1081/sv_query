/**
 * Bounded source evidence for the ids returned by a query.
 *
 * No I/O and no environment access: the caller injects `readSnapshot`,
 * `resolveSource`, `readSource`, and `sourceRoot` so the logic is testable
 * with fakes. Only requested ids are emitted (max 80); each record carries
 * file/line plus a 160-char source line and a +/-2 line context when the
 * source file can be read.
 */

export const MAX_EVIDENCE_NODES = 80;
export const MAX_SOURCE_LINE_CHARS = 160;
export const CONTEXT_RADIUS = 2;

/** Ids whose evidence should be collected, in stable output order. */
export function wantedIds(out) {
  const wanted = [];
  for (const key of ["drivers", "loads", "path"]) {
    for (const id of out[key] || []) if (typeof id === "string") wanted.push(id);
  }
  for (const n of out.nodes || []) if (n && typeof n.id === "string") wanted.push(n.id);
  return wanted;
}

/**
 * Collect evidence for `ids` from the snapshot.
 *
 * Returns `null` when the snapshot metadata is unavailable, otherwise an
 * object keyed by the requested node ids that exist in the snapshot.
 *
 * @param {object} deps
 * @param {string} deps.snapshot snapshot tag
 * @param {string[]} deps.ids requested node ids
 * @param {(tag: string) => Promise<object|null>} deps.readSnapshot
 * @param {(file: string|null, sourceRoot?: string) => string|null} deps.resolveSource
 * @param {(path: string) => Promise<string>} deps.readSource
 * @param {string|undefined} deps.sourceRoot
 */
export async function collectEvidence({
  snapshot,
  ids,
  readSnapshot,
  resolveSource,
  readSource,
  sourceRoot,
}) {
  const snap = await readSnapshot(snapshot);
  if (!snap) return null;
  const byId = new Map((snap.nodes || []).map((n) => [n.id, n]));
  const lines = new Map();
  const evidence = {};
  for (const id of [...new Set(ids)].slice(0, MAX_EVIDENCE_NODES)) {
    const node = byId.get(id);
    if (!node) continue;
    const rec = { file: node.file || null, line: node.line || null };
    const source = resolveSource(node.file, sourceRoot);
    if (source && Number.isInteger(node.line) && node.line > 0) {
      try {
        let content = lines.get(source);
        if (!content) {
          content = (await readSource(source)).split(/\r?\n/);
          lines.set(source, content);
        }
        const text = (content[node.line - 1] || "").trim();
        if (text) rec.source_line = text.slice(0, MAX_SOURCE_LINE_CHARS);
        const startLine = Math.max(1, node.line - CONTEXT_RADIUS);
        const endLine = Math.min(content.length, node.line + CONTEXT_RADIUS);
        rec.source_context = [];
        for (let n = startLine; n <= endLine; n++) {
          const line = (content[n - 1] || "").trim();
          if (line) {
            rec.source_context.push({
              line: n,
              text: line.slice(0, MAX_SOURCE_LINE_CHARS),
            });
          }
        }
      } catch {
        rec.source_missing = true;
      }
    }
    evidence[id] = rec;
  }
  return evidence;
}

/** Add evidence to a compacted query result when `args.evidence` is set. */
export async function addEvidence(out, args, deps) {
  if (!args.evidence) return out;
  const evidence = await collectEvidence({
    ...deps,
    snapshot: args.snapshot,
    ids: wantedIds(out),
  });
  if (!evidence) return { ...out, evidence_error: "snapshot metadata unavailable" };
  return { ...out, evidence };
}
