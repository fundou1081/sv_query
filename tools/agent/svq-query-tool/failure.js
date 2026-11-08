/**
 * Pure failure classification for the constrained svq_query DSH tool.
 *
 * No I/O, no imports: the caller hands over the raw error envelope and gets
 * back the normalized `{ status, code, message, candidates, suggestions }`
 * tuple that the tool renders to the agent.
 *
 * This module exists so the failure contract is testable without importing
 * `index.js` (which pulls in the `@deepseek-ai/dsh-tools` peer dependency).
 */

/** Statuses the tool may report for a failed query. */
export const FAILURE_STATUSES = ["not_found", "ambiguous", "error"];

/** Stable error code used when no better code is available. */
export const GENERIC_ERROR_CODE = "E_QUERY_FAILED";

/** Stable error codes that classify a failure by their code alone. */
const NOT_FOUND_CODES = new Set(["E_SIGNAL_NOT_FOUND"]);
const AMBIGUOUS_CODES = new Set(["E_SIGNAL_AMBIGUOUS"]);

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/**
 * Accept only a stable, non-empty string error code.
 *
 * Node sets `err.code` to a process exit status (a number) when a child
 * process fails, and `execFile` uses `1` for "the command exited non-zero".
 * That number is not an error code, so it must never reach `error.code`.
 *
 * @param {unknown} value Candidate code.
 * @returns {string|null} The code when it is a usable string, else null.
 */
function stableCode(value) {
  return typeof value === "string" && value ? value : null;
}

/**
 * Locate the per-signal row and the per-error entry inside a failure payload.
 *
 * `sv_query trace` reports per-signal failures twice: the row under
 * `result.signals[]` carries `resolution`/`candidates`/`suggestions`, and the
 * entry under `errors[]` carries the stable `error_code`. The top-level
 * `fail()` envelope (`{ ok: false, error, unknown, hint }`) carries neither.
 *
 * @param {unknown} payload Raw `sv_query --json` failure envelope.
 * @returns {{row: object, first: object}}
 */
export function failureParts(payload) {
  if (!isPlainObject(payload)) return { row: {}, first: {} };
  const row = isPlainObject(payload.result?.signals?.[0]) ? payload.result.signals[0] : {};
  const first = isPlainObject(payload.errors?.[0]) ? payload.errors[0] : {};
  return { row, first };
}

/**
 * Classify a failure payload into a status plus a stable error code.
 *
 * The status is derived from, in order:
 *   1. the row's `resolution` (`not_found` / `ambiguous`),
 *   2. the stable `error_code` (`E_SIGNAL_NOT_FOUND` -> not_found,
 *      `E_SIGNAL_AMBIGUOUS` -> ambiguous),
 *   3. the `top_ambiguous` flag (multiple top modules in the snapshot).
 *
 * Anything else is a generic `error`.
 *
 * The code is always a stable string. A numeric or otherwise non-string code
 * (e.g. a child-process exit status) is never propagated.
 *
 * @param {unknown} payload Raw `sv_query --json` failure envelope.
 * @param {string} [fallbackCode] Code used when the payload carries none.
 * @returns {{status: string, code: string}}
 */
export function classifyFailure(payload, fallbackCode = GENERIC_ERROR_CODE) {
  const { row, first } = failureParts(payload);
  const code = stableCode(row.error_code)
    || stableCode(first.error_code)
    || stableCode(fallbackCode)
    || GENERIC_ERROR_CODE;
  let status = "error";
  if (row.resolution === "not_found" || NOT_FOUND_CODES.has(code)) {
    status = "not_found";
  } else if (row.resolution === "ambiguous" || AMBIGUOUS_CODES.has(code)
             || row.top_ambiguous) {
    status = "ambiguous";
  }
  return { status, code };
}

/**
 * Pick the error code for a failure: the payload's stable code first, then
 * the thrown error's `code`, then the generic fallback.
 *
 * Only non-empty strings are accepted. Node sets `err.code` to a numeric exit
 * status when a child process fails, so a numeric code falls back to
 * `E_QUERY_FAILED` instead of leaking `1` into the tool contract.
 *
 * @param {unknown} payload Raw `sv_query --json` failure envelope.
 * @param {Error} [err] The thrown error.
 * @returns {string} A stable `E_*` error code.
 */
export function failureCode(payload, err = undefined) {
  const { row, first } = failureParts(payload);
  return stableCode(row.error_code)
    || stableCode(first.error_code)
    || stableCode(err?.code)
    || GENERIC_ERROR_CODE;
}

/**
 * Normalize the error detail of a failure payload.
 *
 * @param {unknown} payload Raw `sv_query --json` failure envelope.
 * @param {Error} [err] The thrown error, used as a last-resort message.
 * @returns {{message: string, candidates: string[], suggestions: string[]}}
 */
export function failureDetail(payload, err = undefined) {
  const { row, first } = failureParts(payload);
  const message = row.error || first.error || err?.message || "query failed";
  return {
    message,
    candidates: row.candidates || [],
    suggestions: row.suggestions || [],
  };
}

/**
 * Build the tool's failure envelope.
 *
 * The envelope is always lossless JSON: every field is present and no field
 * is `undefined`, so `JSON.stringify` round-trips it unchanged.
 *
 * @param {object} args Tool arguments (`intent`, `snapshot`, `signal`, `dst`).
 * @param {Error} err The thrown error.
 * @param {unknown} [payload] Injected failure envelope. Defaults to
 *   `err.payload` (attached by `compact.js` / `neighborhood.js`).
 * @returns {object} The failure envelope rendered to the agent.
 */
export function failureResult(args, err, payload = undefined) {
  const raw = payload === undefined ? err?.payload : payload;
  const code = failureCode(raw, err);
  const status = classifyFailure(raw, code).status;
  const detail = failureDetail(raw, err);
  return {
    ok: false, status, found: false,
    intent: args.intent, snapshot: args.snapshot,
    signal: args.signal || null, dst: args.dst || null,
    error: {
      code,
      message: detail.message,
      candidates: detail.candidates,
      suggestions: detail.suggestions,
    },
    evidence_available: false,
  };
}
