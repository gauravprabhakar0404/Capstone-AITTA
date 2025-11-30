import sys
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)

# MCP imports (low-level only)
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types import (
    JSONRPCRequest,
    InitializeRequestParams,
    ClientCapabilities,
    CallToolRequestParams,
)

# Envelope type the stdio writer expects
@dataclass
class Outbound:
    message: JSONRPCRequest


def extract_text_content(resp):
    """Extract text content from a tool call response."""
    root = resp.message.root
    result = getattr(root, "result", {})
    content = result.get("content", [])
    text_blocks = [c for c in content if c.get("type") == "text"]
    if not text_blocks:
        return None
    return text_blocks[0].get("text", "")


class MCPClientManager:
    """Manages connections to multiple MCP servers using low-level JSON-RPC."""

    def __init__(self, config):
        self.config = config
        self.servers: Dict[str, StdioServerParameters] = {
            "splunk": StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).parent / "mcp_servers" / "splunk_server.py")],
                env={
                    "SPLUNK_HOST": self.config.SPLUNK_HOST,
                    "SPLUNK_TOKEN": self.config.SPLUNK_TOKEN,
                },
            ),
            "jira": StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).parent / "mcp_servers" / "jira_server.py")],
                env={
                    "JIRA_URL": self.config.JIRA_URL,
                    "JIRA_EMAIL": self.config.JIRA_EMAIL,
                    "JIRA_API_TOKEN": self.config.JIRA_API_TOKEN,
                },
            ),
            "cmdb": StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).parent / "mcp_servers" / "cmdb_server.py")],
                 env={
                    "CMDB_API_URL": self.config.CMDB_API_URL,
                    "CMDB_USERNAME": self.config.CMDB_USERNAME,
                    "CMDB_PASSWORD": self.config.CMDB_PASSWORD,
                    "USE_MOCK_CMDB": str(self.config.USE_MOCK_CMDB),
                },

            ),
        }

    async def _initialize(self, read_stream, write_stream):
        """Send initialize message to server."""
        init_params = InitializeRequestParams(
            protocolVersion="2024-11-05",
            clientInfo={"name": "AITTA Client", "version": "0.1"},
            capabilities=ClientCapabilities(),
        )
        init_msg = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize", params=init_params.model_dump()
        )
        await write_stream.send(Outbound(message=init_msg))
        return await read_stream.receive()

    async def list_tools(self, server_name: str):
        """List tools available on a server."""
        server_params = self.servers[server_name]
        async with stdio_client(server_params) as (read_stream, write_stream):
            await self._initialize(read_stream, write_stream)

            list_msg = JSONRPCRequest(jsonrpc="2.0", id=2, method="tools/list", params={})
            await write_stream.send(Outbound(message=list_msg))
            resp = await read_stream.receive()
            return extract_text_content(resp)

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]):
        """Call a tool on a server."""
        server_params = self.servers[server_name]
        async with stdio_client(server_params) as (read_stream, write_stream):
            await self._initialize(read_stream, write_stream)

            call_params = CallToolRequestParams(name=tool_name, arguments=arguments)
            call_msg = JSONRPCRequest(
                jsonrpc="2.0", id=3, method="tools/call", params=call_params.model_dump()
            )
            await write_stream.send(Outbound(message=call_msg))
            resp = await read_stream.receive()
            return extract_text_content(resp)

    async def cleanup(self):
        """No persistent sessions in low-level mode, so nothing to clean up."""
        logger.info("Cleanup not required in low-level mode")