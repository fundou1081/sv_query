"""sv_query package namespace (P165.2).

The query engine lives in ``sv_query.trace``.  The old top-level ``trace``
package collided with Python's stdlib ``trace`` module and is removed.

P183.4 exposes the transport-agnostic :class:`sv_query.session.Session`.
"""
from .session import Session

__all__ = ["Session"]
