"""Layer-neutral error vocabulary for `sv_query.Session` responses (P183.4 / D12).

This module is the **single source** for the three error codes the library
`Session` can emit and for their envelope ``error.type`` names.  It has no
imports at all, so it can be consumed by the library, the CLI, or an external
transport without dragging in the CLI, Typer, the engine, or process globals.

Consumers must reference these constants instead of re-writing the string
literals; ``sv_query.cli.errors.ErrorCode`` mirrors them by value and a contract test
(``test_d12_error_envelope.py``) locks the agreement.

Response shape emitted by ``Session`` (library layer) uses ``error`` as a
**dict** (``{"type": ..., "message": ...}``).  The CLI transport envelope
(``cli._output.fail``) keeps ``error`` as a **string**.  D12 unifies the code
vocabulary and the message source, not the container type.
"""

#: Request is not a mapping / lacks a non-empty string ``op`` / bad ``request_id``.
E_INVALID_REQUEST = "E_INVALID_REQUEST"

#: ``op`` is a valid string but the session has no built-in or injected handler.
E_UNSUPPORTED_OP = "E_UNSUPPORTED_OP"

#: An injected handler raised, or returned a non-mapping result.
E_HANDLER_FAILED = "E_HANDLER_FAILED"

#: A graph query endpoint does not exist (paths/dataflow). (P194.5g)
E_SIGNAL_NOT_FOUND = "E_SIGNAL_NOT_FOUND"

#: The complete vocabulary the library `Session` may emit.
SESSION_ERROR_CODES = frozenset({
    E_INVALID_REQUEST,
    E_UNSUPPORTED_OP,
    E_HANDLER_FAILED,
    E_SIGNAL_NOT_FOUND,
})

#: Public ``error.type`` name for each code (locked by contract test).
ERROR_TYPES = {
    E_INVALID_REQUEST: "InvalidRequest",
    E_UNSUPPORTED_OP: "UnsupportedOperation",
    E_HANDLER_FAILED: "HandlerFailed",
    E_SIGNAL_NOT_FOUND: "SignalNotFound",
}
