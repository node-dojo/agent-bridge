# SPDX-License-Identifier: GPL-3.0-or-later
"""Agent Bridge MCP server: blmcp with a registry-backed connection resolver."""

from .resolver import Resolver, TargetError

RESOLVER = Resolver()


def patched_get_connection_params():
    """Replacement for blmcp's get_connection_params: route to the sticky target.

    blmcp's send_code() calls get_connection_params() unqualified at call time,
    so replacing the module attribute lands for every tool (including the 17
    that import send_code by name).
    """
    try:
        return RESOLVER.resolve()
    except TargetError as ex:
        # Translate to blmcp's error type so its ConnectionError-based fallbacks
        # and messages behave. send_code raises ConnectionError on socket issues;
        # a missing target is the same class of "cannot reach Blender" problem.
        raise ConnectionError(str(ex)) from ex


def install_patch() -> None:
    from blmcp.tools_helpers import connection
    connection.get_connection_params = patched_get_connection_params


def main() -> int:
    install_patch()
    # Register bridge-specific tools onto blmcp's mcp before it runs.
    from . import bridge_tools
    bridge_tools.install(RESOLVER)
    import blmcp
    return blmcp.main()
