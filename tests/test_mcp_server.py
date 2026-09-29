"""End-to-end test of mcp_server/server.py over stdio, like a real MCP client.

Needs the `mcp` package (pip install -r mcp_server/requirements.txt) and the
abqpy stubs in <kit>/.abqpy; skipped otherwise.

    python -m unittest tests.test_mcp_server
"""

import asyncio
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
SERVER = os.path.join(KIT, 'mcp_server', 'server.py')

try:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    HAVE_MCP = True
except ImportError:
    HAVE_MCP = False

HAVE_STUBS = os.path.isdir(os.path.join(KIT, '.abqpy', 'abaqus'))


async def _session_calls(calls):
    params = StdioServerParameters(command=sys.executable, args=[SERVER])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            results = []
            for name, args in calls:
                res = await session.call_tool(name, args)
                results.append(''.join(getattr(c, 'text', '') for c in res.content))
            return init, tools, results


@unittest.skipUnless(HAVE_MCP, 'mcp package not installed')
class McpServerTests(unittest.TestCase):
    def test_tools_are_listed_read_only_with_instructions(self):
        init, tools, _ = asyncio.run(_session_calls([]))
        names = sorted(t.name for t in tools.tools)
        self.assertEqual(names, ['abaqus_api_areas', 'abaqus_api_list_area',
                                 'abaqus_api_lookup', 'abaqus_api_search'])
        for t in tools.tools:
            self.assertTrue(t.annotations.read_only_hint, t.name)
            self.assertTrue(t.description)
        self.assertIn('abaqus_api_lookup', init.instructions)

    @unittest.skipUnless(HAVE_STUBS, 'abqpy stubs not installed in .abqpy')
    def test_calls_return_api_documentation(self):
        _, _, (areas, contact, lookup, missing) = asyncio.run(_session_calls([
            ('abaqus_api_areas', {}),
            ('abaqus_api_list_area', {'area': 'Interaction'}),
            ('abaqus_api_lookup', {'name': 'Coupling'}),
            ('abaqus_api_lookup', {'name': 'NoSuchThing'}),
        ]))
        self.assertIn('Material', areas)
        self.assertIn('ContactProperty', contact)
        self.assertIn('rotationalCouplingType', lookup)
        self.assertIn('versionadded', lookup)
        self.assertIn('No class or method', missing)


if __name__ == '__main__':
    unittest.main()
