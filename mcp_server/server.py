"""Abaqus MCP server - step 1: offline API lookup tools.

Runs in ordinary Python 3.10+ (not Abaqus Python) on the machine where
agents run; later steps call Abaqus through `abaqus cae noGUI`.

    pip install -r mcp_server/requirements.txt
    python mcp_server/server.py          # stdio transport, started by the MCP client

Tools in this step are read-only and need no Abaqus installation, only
the abqpy stubs (see tools/api_lookup.py).
"""

import glob
import os
import sys

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

KIT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KIT_DIR, 'tools'))
import api_lookup  # noqa: E402

INSTRUCTIONS = """Tools for Abaqus/CAE scripting.

Use the abaqus_api_* tools to find and read the official Abaqus Scripting
API (from abqpy stubs matching the user's Abaqus version) before writing
or explaining any Abaqus Python call. Typical flow: abaqus_api_search
(or abaqus_api_areas -> abaqus_api_list_area) to find the right
class/method, then abaqus_api_lookup for its signature, arguments,
members and the version it was added in. Don't guess argument names.
"""

server = MCPServer(name='abaqus', instructions=INSTRUCTIONS)
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                            idempotent_hint=True, open_world_hint=False)


def _stubs():
    """(stub root, abqpy version) or (None, None) when the stubs aren't installed."""
    root = api_lookup.find_stub_root()
    if root is None:
        return None, None
    info = glob.glob(os.path.join(root, 'abqpy-*.dist-info'))
    version = os.path.basename(info[0])[len('abqpy-'):-len('.dist-info')] if info else 'unknown'
    return root, version


def _run(fn, *args):
    root, version = _stubs()
    if root is None:
        return api_lookup.SETUP_HINT
    text, _ = fn(root, *args)
    return '[abqpy stubs %s]\n%s' % (version, text)


@server.tool(annotations=READ_ONLY)
def abaqus_api_areas() -> str:
    """List the areas of the Abaqus Scripting API (Material, Interaction, Step, Load, ...) with how many object-creating methods each has."""
    return _run(api_lookup.areas)


@server.tool(annotations=READ_ONLY)
def abaqus_api_list_area(area: str) -> str:
    """List every object-creating method (constructor) in one API area with a one-line summary, e.g. area='Interaction' for contact."""
    return _run(api_lookup.list_area, area)


@server.tool(annotations=READ_ONLY)
def abaqus_api_search(query: str, in_summaries: bool = True) -> str:
    """Find Abaqus API classes/methods whose name (and, by default, one-line summary) contains query, e.g. 'contact', 'Csys', 'frequency'."""
    return _run(api_lookup.search, query, in_summaries)


@server.tool(annotations=READ_ONLY)
def abaqus_api_lookup(name: str) -> str:
    """Full documentation of an Abaqus class or method by exact name: signature, arguments, class members, access path, versionadded notes."""
    return _run(api_lookup.lookup, name, 200)


def main():
    server.run(transport='stdio')


if __name__ == '__main__':
    main()
