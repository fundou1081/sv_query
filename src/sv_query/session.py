"""Transport-agnostic `Session` request/response seam (P183.4 / D10).

This module is deliberately pure: it does not import the CLI, Typer,
`sys.argv`, environment variables, or process-global configuration.  The
only supported operation is the read-only `version` probe.

Request shape::

    {"op": "version", "request_id": "optional-string"}

Response shape always a plain ``dict``::

    success: {"ok": True,  "op": "version", "request_id"?: str, "result": {...}}
    failure: {"ok": False, "op"?: str, "request_id"?: str,
              "error_code": str, "error": {"type": str, "message": str}}

Invalid input never raises for the caller; it maps to a structured
``E_INVALID_REQUEST`` / ``E_UNSUPPORTED_OP`` response.
"""
from __future__ import annotations

from collections.abc import Mapping

SESSION_CONTRACT_VERSION = "1.0"

# Explicit runtime constant, deliberately not read from installation metadata
# or the environment so `version` stays deterministic.  Kept in sync with
# ``pyproject.toml [project].version`` by a contract test.
PACKAGE_VERSION = "0.3.0"

E_INVALID_REQUEST = "E_INVALID_REQUEST"
E_UNSUPPORTED_OP = "E_UNSUPPORTED_OP"

_ERROR_TYPES = {
    E_INVALID_REQUEST: "InvalidRequest",
    E_UNSUPPORTED_OP: "UnsupportedOperation",
}

_MISSING = object()


class Session:
    """Stateless entry point for transport-independent requests."""

    @staticmethod
    def execute(request: Mapping[str, object]) -> dict[str, object]:
        """Execute one request and return a structured response.

        ``request`` must be a mapping with a non-empty string ``op``.  An
        optional ``request_id`` must be a string and is echoed on both
        success and failure.
        """
        if not isinstance(request, Mapping):
            return _failure(None, _MISSING, E_INVALID_REQUEST, "request must be a mapping")

        try:
            raw_op = request.get("op", _MISSING)
            op = raw_op if isinstance(raw_op, str) else None

            raw_request_id = request.get("request_id", _MISSING)
            request_id_invalid = "request_id" in request and not isinstance(raw_request_id, str)
            request_id = raw_request_id if isinstance(raw_request_id, str) else _MISSING
        except Exception as exc:
            # A hostile Mapping must not escape as a bare exception: the
            # contract promises a structured E_INVALID_REQUEST response.
            return _failure(
                None, _MISSING, E_INVALID_REQUEST,
                f"request access failed: {type(exc).__name__}: {exc}",
            )

        if not isinstance(raw_op, str) or not raw_op:
            return _failure(
                op,
                request_id,
                E_INVALID_REQUEST,
                "request must contain a non-empty string 'op'",
            )

        if request_id_invalid:
            return _failure(
                op,
                _MISSING,
                E_INVALID_REQUEST,
                "request_id must be a string",
            )

        if op == "version":
            return _success(op, request_id, _version_result())

        return _failure(op, request_id, E_UNSUPPORTED_OP, f"unsupported op: {op}")


def _success(op: str, request_id: object, result: dict[str, object]) -> dict[str, object]:
    response: dict[str, object] = {"ok": True, "op": op}
    if request_id is not _MISSING:
        response["request_id"] = request_id
    response["result"] = result
    return response


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
