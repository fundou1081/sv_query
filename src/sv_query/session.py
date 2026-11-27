"""Transport-agnostic `Session` request/response seam (P183.4 / D10 + D11).

This module is deliberately pure: it does not import the CLI, Typer,
`sys.argv`, environment variables, or process-global configuration.
``version`` is served by the session itself; additional operations are
supplied by the caller through injected handlers (D11) so that this module
never has to import CLI command modules.

Request shape::

    {"op": "version",   "request_id": "optional-string"}
    {"op": "<handler>", "request_id": "optional-string", ...handler options}

Response shape always a plain ``dict``::

    success: {"ok": True,  "op": "version", "request_id"?: str, "result": {...}}
    failure: {"ok": False, "op"?: str, "request_id"?: str,
              "error_code": str, "error": {"type": str, "message": str}}

Invalid request **data** never raises for the caller; it maps to a
structured ``E_INVALID_REQUEST`` / ``E_UNSUPPORTED_OP`` response.  A handler
failure (exception or non-mapping result) maps to ``E_HANDLER_FAILED``.
The four codes and their ``error.type`` names live in
:mod:`sv_query.errors` (single source, no imports); this module only
re-exports them.
Invalid constructor arguments (non-mapping handlers, non-callable handler,
or an attempt to override the built-in ``version`` op) raise ``TypeError`` /
``ValueError`` because those are programming errors, not requests.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from . import errors as _errors

SESSION_CONTRACT_VERSION = "1.0"

# Explicit runtime constant, deliberately not read from installation metadata
# or the environment so `version` stays deterministic.  Kept in sync with
# ``pyproject.toml [project].version`` by a contract test.
PACKAGE_VERSION = "0.3.8"

# Re-exported for the D10/D11 import path (`from sv_query.session import E_*`);
# the values themselves are single-sourced from :mod:`sv_query.errors`.
E_INVALID_REQUEST = _errors.E_INVALID_REQUEST
E_UNSUPPORTED_OP = _errors.E_UNSUPPORTED_OP
E_HANDLER_FAILED = _errors.E_HANDLER_FAILED
E_SIGNAL_NOT_FOUND = _errors.E_SIGNAL_NOT_FOUND
_ERROR_TYPES = _errors.ERROR_TYPES

logger = logging.getLogger(__name__)

_BUILTIN_OPS = frozenset({"version"})

#: Query ops exposed by GraphSession / `session --serve` (P194.2e).
SESSION_QUERY_OPS = frozenset({
    "graph_nodes", "graph_edges", "drivers", "loads", "paths", "dataflow",
    "instances", "scope", "verify_claim", "verify_consistency",
})

#: CLI capabilities that the local session deliberately does not expose yet.
SESSION_UNSUPPORTED_OPS = frozenset({"stats"})

#: Machine-readable protocol contract; surfaced through capabilities.json_contract.
SESSION_CONTRACT = {
    "transport": "stdio-json-lines",
    "entrypoint": "sv_query session --serve --filelist PATH [--no-cache]",
    "ops": sorted(SESSION_QUERY_OPS),
    "builtin_ops": sorted(_BUILTIN_OPS),
    "unsupported_ops": sorted(SESSION_UNSUPPORTED_OPS),
    "request": {
        "op": "graph_nodes|graph_edges|drivers|loads|paths|dataflow|version",
        "request_id": "optional string, echoed on success/failure",
        "arguments": "op-specific fields; see sv_query capabilities --json",
    },
    "success": {"ok": True, "op": "string", "result": "object"},
    "failure": {
        "ok": False,
        "op": "string when known; omitted when the request cannot be parsed",
        "error_code": "E_INVALID_REQUEST|E_UNSUPPORTED_OP|E_HANDLER_FAILED|E_SIGNAL_NOT_FOUND",
        "error": {"type": "string", "message": "string"},
    },
    "notes": [
        "one graph per process; refresh checks source identity per request",
        "snapshot sessions are immutable",
        "signals/scope/instances/verify ops use the same one graph",
    ],
}

#: Injected handler: request mapping in, result mapping out.
Handler = Callable[[Mapping[str, object]], Mapping[str, object]]

_MISSING = object()


class Session:
    """Entry point for transport-independent requests.

    ``handlers`` maps an operation name to a callable that receives the
    original request mapping and returns the result mapping.  ``version`` is
    built in and cannot be overridden.
    """

    def __init__(self, handlers: Mapping[str, Handler] | None = None) -> None:
        self._handlers: dict[str, Handler] = {}
        if handlers is None:
            return
        if not isinstance(handlers, Mapping):
            raise TypeError("handlers must be a mapping of op name to callable")
        for name, handler in handlers.items():
            if not isinstance(name, str) or not name:
                raise TypeError("handler keys must be non-empty strings")
            if name in _BUILTIN_OPS:
                raise ValueError(f"op {name!r} is built in and cannot be overridden")
            if not callable(handler):
                raise TypeError(f"handler for op {name!r} must be callable")
        self._handlers = dict(handlers)

    def execute(self, request: Mapping[str, object]) -> dict[str, object]:
        """Execute one request and return a structured response.

        ``request`` must be a mapping with a non-empty string ``op``.  An
        optional ``request_id`` must be a string and is echoed on both
        success and failure.  A handler's result is copied to a new
        top-level ``dict``; nested mutable values are intentionally not
        deep-copied.
        """
        failure, op, request_id = _parse_request(request)
        if failure is not None:
            return failure
        assert op is not None
        if op == "version":
            return _success(op, request_id, _version_result())
        handler = self._handlers.get(op)
        if handler is None:
            return _failure(op, request_id, E_UNSUPPORTED_OP, f"unsupported op: {op}")
        return _run_handler(op, request_id, handler, request)


def _parse_request(
    request: object,
) -> tuple[dict[str, object] | None, str | None, object]:
    """Validate the request envelope; return ``(failure, op, request_id)``."""
    if not isinstance(request, Mapping):
        return _failure(None, _MISSING, E_INVALID_REQUEST, "request must be a mapping"), None, _MISSING

    try:
        raw_op = request.get("op", _MISSING)
        op = raw_op if isinstance(raw_op, str) else None

        raw_request_id = request.get("request_id", _MISSING)
        request_id_invalid = "request_id" in request and not isinstance(raw_request_id, str)
        request_id = raw_request_id if isinstance(raw_request_id, str) else _MISSING
    except Exception as exc:
        # A hostile Mapping must not escape as a bare exception: the
        # contract promises a structured E_INVALID_REQUEST response.
        logger.debug("request mapping access failed: %s", exc)
        return (
            _failure(
                None, _MISSING, E_INVALID_REQUEST,
                f"request access failed: {type(exc).__name__}: {exc}",
            ),
            None,
            _MISSING,
        )

    if not isinstance(raw_op, str) or not raw_op:
        return (
            _failure(
                op,
                request_id,
                E_INVALID_REQUEST,
                "request must contain a non-empty string 'op'",
            ),
            None,
            _MISSING,
        )

    if request_id_invalid:
        return (
            _failure(op, _MISSING, E_INVALID_REQUEST, "request_id must be a string"),
            None,
            _MISSING,
        )

    return None, op, request_id


def _run_handler(
    op: str,
    request_id: object,
    handler: Handler,
    request: Mapping[str, object],
) -> dict[str, object]:
    """Call one injected handler once and normalize its result."""
    try:
        raw_result = handler(request)
    except Exception as exc:
        code = getattr(exc, "error_code", E_HANDLER_FAILED)
        if code not in _ERROR_TYPES:
            code = E_HANDLER_FAILED
        return _failure(
            op, request_id, code,
            f"handler for op {op!r} raised {type(exc).__name__}: {exc}",
        )

    if not isinstance(raw_result, Mapping):
        return _failure(
            op, request_id, E_HANDLER_FAILED,
            f"handler for op {op!r} returned {type(raw_result).__name__}, "
            "expected a mapping",
        )

    try:
        result = dict(raw_result)
    except Exception as exc:
        logger.debug("handler result copy failed for %r: %s", op, exc)
        return _failure(
            op, request_id, E_HANDLER_FAILED,
            f"handler for op {op!r} result could not be copied: "
            f"{type(exc).__name__}: {exc}",
        )

    return _success(op, request_id, result)


def _success(op: str, request_id: object, result: dict[str, object]) -> dict[str, object]:
    response: dict[str, object] = {"ok": True, "op": op}
    if request_id is not _MISSING:
        response["request_id"] = request_id
    response["result"] = result
    return response


def error_response(
    op: str | None,
    error_code: str,
    message: str,
    request_id: str | None = None,
) -> dict[str, object]:
    """Build the public failure envelope (same shape as Session.execute)."""
    rid = _MISSING if request_id is None else request_id
    return _failure(op, rid, error_code, message)


def _failure(
    op: str | None,
    request_id: object,
    error_code: str,
    message: str,
) -> dict[str, object]:
    response: dict[str, object] = {"ok": False}
    if op is not None:
        response["op"] = op
    if request_id is not _MISSING:
        response["request_id"] = request_id
    response["error_code"] = error_code
    response["error"] = {"type": _ERROR_TYPES[error_code], "message": message}
    return response


def _version_result() -> dict[str, object]:
    return {
        "schema_version": SESSION_CONTRACT_VERSION,
        "package_version": PACKAGE_VERSION,
    }
