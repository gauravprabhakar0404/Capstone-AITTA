import asyncio
import sys
from dataclasses import dataclass
import json

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types import JSONRPCRequest, InitializeRequestParams, ClientCapabilities, CallToolRequestParams

# Envelope type the stdio writer expects
@dataclass
class Outbound:
    message: JSONRPCRequest


def extract_json_from_call_response(call_resp):
    """Extract and parse JSON text from a call_tool response."""
    root = call_resp.message.root  # JSONRPCResponse
    result = getattr(root, "result", {})
    content = result.get("content", [])
    text_blocks = [c for c in content if c.get("type") == "text"]
    if not text_blocks:
        return None
    text = text_blocks[0].get("text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = text.replace(",\n    ,", ",").strip()
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return {"raw_text": text}


async def call_tool(write_stream, read_stream, name, arguments, req_id):
    """Helper to call a tool and parse response."""
    call_params = CallToolRequestParams(name=name, arguments=arguments)
    call_msg = JSONRPCRequest(
        jsonrpc="2.0",
        id=req_id,
        method="tools/call",
        params=call_params.model_dump()
    )
    await write_stream.send(Outbound(message=call_msg))
    call_resp = await read_stream.receive()
    print(f"\nTool '{name}' response:", call_resp)
    parsed = extract_json_from_call_response(call_resp)
    if parsed:
        print(json.dumps(parsed, indent=2))


async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["../aitta_mcp/mcp_servers/splunk_server.py"]
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        print("Got streams:", read_stream, write_stream)

        # 1. Initialize
        init_params = InitializeRequestParams(
            protocolVersion="2024-11-05",
            clientInfo={"name": "AITTA Client", "version": "0.1"},
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
        list_msg = JSONRPCRequest(jsonrpc="2.0", id=2, method="tools/list", params={})
        await write_stream.send(Outbound(message=list_msg))
        list_resp = await read_stream.receive()
        print("Tools response:", list_resp)

        # 3. Call each tool
        await call_tool(write_stream, read_stream, "query_logs",
                        {"host": "prod-web-01", "time_range": "30m", "search_query": "*", "index": "main"}, 3)

        await call_tool(write_stream, read_stream, "search_recent",
                        {"search_term": "error", "time_range": "15m", "max_results": 5}, 4)

        await call_tool(write_stream, read_stream, "get_alert_details",
                        {"alert_id": "alert-123"}, 5)

        await call_tool(write_stream, read_stream, "search_errors",
                        {"host": "prod-web-01", "error_pattern": "OutOfMemory", "time_range": "1h"}, 6)

        await call_tool(write_stream, read_stream, "send_event",
                        {"event": "Test event from client", "sourcetype": "aitta:test", "host": "aitta-agent"}, 7)


if __name__ == "__main__":
    asyncio.run(main())