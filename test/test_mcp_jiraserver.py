import asyncio
import sys
import json
from dataclasses import dataclass

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


async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["../aitta_mcp/mcp_servers/jira_server.py"]  # adjust path to your Jira server file
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        print("Got streams:", read_stream, write_stream)

        # 1. Initialize
        init_params = InitializeRequestParams(
            protocolVersion="2024-11-05",
            clientInfo={"name": "AITTA Jira Client", "version": "0.1"},
            capabilities=ClientCapabilities()
        )
        init_msg = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="initialize",
            params=init_params.model_dump()
        )
        await write_stream.send(Outbound(message=init_msg))
        init_resp = await read_stream.receive()
        print("Initialize response:", init_resp)

        # 2. List tools
        list_msg = JSONRPCRequest(
            jsonrpc="2.0",
            id=2,
            method="tools/list",
            params={}
        )
        await write_stream.send(Outbound(message=list_msg))
        list_resp = await read_stream.receive()
        print("Tools response:", list_resp)

        # 3. Call tool: get_current_user
        call_params = CallToolRequestParams(name="get_current_user", arguments={})
        call_msg = JSONRPCRequest(
            jsonrpc="2.0",
            id=3,
            method="tools/call",
            params=call_params.model_dump()
        )
        await write_stream.send(Outbound(message=call_msg))
        call_resp = await read_stream.receive()
        print("Raw get_current_user response:", call_resp)
        print("Parsed:", extract_text_content(call_resp))

        # 4. Call tool: create_ticket (mock mode if no token)
        ticket_args = {
            "project": "KAG",
            "summary": "Sample issue from MCP client",
            "description": "This is a test issue created via MCP client",
            "priority": "High",
            "assignee": "",
            "issue_type": "Bug"
        }
        call_params = CallToolRequestParams(name="create_ticket", arguments=ticket_args)
        call_msg = JSONRPCRequest(
            jsonrpc="2.0",
            id=4,
            method="tools/call",
            params=call_params.model_dump()
        )
        await write_stream.send(Outbound(message=call_msg))
        call_resp = await read_stream.receive()
        print("Raw create_ticket response:", call_resp)
        print("Parsed:", extract_text_content(call_resp))


if __name__ == "__main__":
    asyncio.run(main())