import sys
import asyncio
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types import JSONRPCRequest, InitializeRequestParams, ClientCapabilities, CallToolRequestParams

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_cmdb_client")
load_dotenv()

def extract_text_content(resp):
    """
    Extracts the first 'text' block from the MCP result content.
    Falls back to raw JSON if shape differs.
    """
    try:
        root = resp.message.root
        result = getattr(root, "result", {}) or {}
        content = result.get("content", [])
        blocks = [c for c in content if c.get("type") == "text"]
        if blocks:
            return blocks[0].get("text", "")
        return json.dumps(result)
    except Exception:
        # In case resp structure differs, dump whole object for debugging
        try:
            return json.dumps(resp.message.root)
        except Exception:
            return str(resp)

async def initialize(read_stream, write_stream):
    init_params = InitializeRequestParams(
        protocolVersion="2024-11-05",
        clientInfo={"name": "AITTA Test Client", "version": "0.1"},
        capabilities=ClientCapabilities(),
    )
    init_msg = JSONRPCRequest(jsonrpc="2.0", id=1, method="initialize", params=init_params.model_dump())
    await write_stream.send(type("Outbound", (), {"message": init_msg})())
    resp = await read_stream.receive()
    logger.info(f"Initialized: {resp}")
    return resp

async def call_tool(read_stream, write_stream, name, arguments, req_id):
    params = CallToolRequestParams(name=name, arguments=arguments)
    call_msg = JSONRPCRequest(jsonrpc="2.0", id=req_id, method="tools/call", params=params.model_dump())
    logger.info(f"Calling tool: {name} {arguments}")
    await write_stream.send(type("Outbound", (), {"message": call_msg})())
    resp = await read_stream.receive()
    text = extract_text_content(resp)
    print(f"\n--- {name} ---\n{text}\n")
    return text

async def main():
    # Launch server subprocess; cmdb_server.py loads its .env itself
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["../aitta_mcp/mcp_servers/cmdb_server.py"] ,
        env={},  # keep empty; cmdb_server.py will read .env
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        await initialize(read_stream, write_stream)

        # 1) get_asset_info
        await call_tool(read_stream, write_stream, "get_asset_info", {"hostname": "prod-web-01"}, req_id=2)

        # 2) get_owner_team
        await call_tool(read_stream, write_stream, "get_owner_team", {"hostname": "prod-web-01"}, req_id=3)

        # 3) get_dependencies
        await call_tool(read_stream, write_stream, "get_dependencies", {"hostname": "prod-web-01"}, req_id=4)

        # 4) create_incident
        await call_tool(
            read_stream,
            write_stream,
            "create_incident",
            {
                "short_description": "AITTA test incident for prod-web-01",
                "description": "Created via MCP stdio client",
                "hostname": "prod-web-01",
                "urgency": "3",
                "impact": "3",
            },
            req_id=5,
        )

if __name__ == "__main__":
    asyncio.run(main())