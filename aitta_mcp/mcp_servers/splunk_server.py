"""
Production Splunk MCP Server - Dual Authentication
Splunk HEC (HTTP Event Collector): https://localhost:8088
Splunk REST API: https://localhost:8089
Uses SPLUNK_TOKEN for HEC ingestion
Uses SPLUNK_USERNAME / SPLUNK_PASSWORD for REST API queries
"""

import asyncio
import json
from dotenv import load_dotenv
import os
import logging
from datetime import datetime, timedelta
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from typing import Any, Sequence
import requests
import urllib3

# Disable SSL warnings for local Splunk
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Configuration from environment
SPLUNK_HOST = os.getenv("SPLUNK_HOST", "https://localhost:8089")  # REST API port
SPLUNK_HEC_URL = os.getenv("SPLUNK_HEC_URL", "https://localhost:8088")  # HEC endpoint
SPLUNK_TOKEN = os.getenv("SPLUNK_TOKEN", "")  # HEC token for ingestion
SPLUNK_USERNAME = os.getenv("SPLUNK_USERNAME", "")
SPLUNK_PASSWORD = os.getenv("SPLUNK_PASSWORD", "")

SPLUNK_VERIFY_SSL = os.getenv("SPLUNK_VERIFY_SSL", "false").lower() == "true"
USE_MOCK = os.getenv("USE_MOCK_SPLUNK", "false").lower() == "true"

print(f"SPLUNK_VERIFY_SSL={SPLUNK_VERIFY_SSL}, USE_MOCK={USE_MOCK}")
print(f"SPLUNK_USERNAME={SPLUNK_USERNAME}, SPLUNK_PASSWORD={SPLUNK_PASSWORD}")
print(f"SPLUNK_HOST={SPLUNK_HOST}")
# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SplunkMCPServer:
    def __init__(self):
        self.server = Server("splunk-server")
        self.has_token = bool(SPLUNK_TOKEN)
        self.has_userpass = bool(SPLUNK_USERNAME and SPLUNK_PASSWORD)
        self.setup_tools()

        if not self.has_token and not self.has_userpass:
            logger.warning("No Splunk credentials provided, using mock mode")
        else:
            logger.info(f"Splunk MCP Server initialized - Host: {SPLUNK_HOST}, HEC: {SPLUNK_HEC_URL}")
            if self.has_token:
                logger.info(f"Using HEC token: {SPLUNK_TOKEN[:10]}...{SPLUNK_TOKEN[-5:]}")
            if self.has_userpass:
                logger.info(f"Using REST API user: {SPLUNK_USERNAME}")    

    def _get_auth(self):
        """Return Basic Auth tuple if username/password are set"""
        if self.has_userpass:
            return (SPLUNK_USERNAME, SPLUNK_PASSWORD)
        return None

    def setup_tools(self):
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="query_logs",
                    description="Query Splunk logs for a specific host and time range using REST API",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "host": {"type": "string", "description": "Hostname to query"},
                            "time_range": {"type": "string", "description": "Time range (e.g., 30m, 1h, 24h)", "default": "30m"},
                            "search_query": {"type": "string", "description": "SPL search query", "default": "*"},
                            "index": {"type": "string", "description": "Splunk index to search", "default": "main"}
                        },
                        "required": ["host"]
                    }
                ),
                Tool(
                    name="search_recent",
                    description="Search recent events across all indexes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_term": {"type": "string", "description": "Term to search for"},
                            "time_range": {"type": "string", "description": "Time range (e.g., 15m, 1h)", "default": "15m"},
                            "max_results": {"type": "integer", "description": "Maximum results", "default": 100}
                        },
                        "required": ["search_term"]
                    }
                ),
                Tool(
                    name="get_alert_details",
                    description="Get details of a specific Splunk alert",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "alert_id": {"type": "string", "description": "Alert ID"}
                        },
                        "required": ["alert_id"]
                    }
                ),
                Tool(
                    name="search_errors",
                    description="Search for error patterns in logs",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "host": {"type": "string", "description": "Hostname"},
                            "error_pattern": {"type": "string", "description": "Error pattern to search for"},
                            "time_range": {"type": "string", "default": "1h"}
                        },
                        "required": ["host", "error_pattern"]}
                ),
                Tool(
                    name="send_event",
                    description="Send event to Splunk HEC",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "event": {"type": "string", "description": "Event data"},
                            "sourcetype": {"type": "string", "description": "Source type", "default": "aitta:test"},
                            "host": {"type": "string", "description": "Host name", "default": "aitta-agent"}
                        },
                        "required": ["event"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
            if name == "query_logs":
                return await self.query_logs(arguments)
            elif name == "search_recent":
                return await self.search_recent(arguments)
            elif name == "get_alert_details":
                return await self.get_alert_details(arguments)
            elif name == "search_errors":
                return await self.search_errors(arguments)
            elif name == "send_event":
                return await self.send_event(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

    async def query_logs(self, args: dict) -> Sequence[TextContent]:
        """Query Splunk logs via REST API using Basic Auth"""
        host = args.get("host")
        time_range = args.get("time_range", "30m")
        search_query = args.get("search_query", "*")
        index = args.get("index", "main")

        if USE_MOCK or not self.has_userpass:
            return await self._mock_query_logs(host, time_range, search_query)

        try:
            spl_query = f'search index={index}  {search_query} | head 100 | table _time, host, source, sourcetype, _raw'
            search_url = f"{SPLUNK_HOST}/services/search/jobs"

            response = requests.post(
                search_url,
                auth=self._get_auth(),
                data={
                    "search": spl_query,
                    "earliest_time": f"-{time_range}",
                    "latest_time": "now",
                    "output_mode": "json"
                },
                verify=SPLUNK_VERIFY_SSL
            )

            if response.status_code not in [200, 201]:
                logger.error(f"Search job creation failed: {response.status_code} - {response.text}")
                return await self._mock_query_logs(host, time_range, search_query)

            job_id = response.json().get("sid")
            if not job_id:
                logger.error(f"No job ID returned: {response.text}")
                return await self._mock_query_logs(host, time_range, search_query)

            # Poll briefly, or go straight to results (Splunk will buffer)
            await asyncio.sleep(2)

            results_url = f"{SPLUNK_HOST}/services/search/jobs/{job_id}/results"
            results_response = requests.get(
                results_url,
                auth=self._get_auth(),
                params={"output_mode": "json"},
                verify=SPLUNK_VERIFY_SSL
            )

            if results_response.status_code != 200:
                logger.error(f"Failed to fetch results: {results_response.status_code} - {results_response.text}")
                return await self._mock_query_logs(host, time_range, search_query)

            results = results_response.json().get("results", [])
            logs = []
            for result in results:
                logs.append({
                    "timestamp": result.get("_time", datetime.now().isoformat()),
                    "level": "ERROR" if "error" in result.get("_raw", "").lower() else "INFO",
                    "message": result.get("_raw", "")[:500],
                    "source": result.get("source", ""),
                    "sourcetype": result.get("sourcetype", ""),
                    "host": result.get("host", host)
                })

            return [TextContent(
                type="text",
                text=json.dumps({
                    "host": host,
                    "time_range": time_range,
                    "query": spl_query,
                    "results_count": len(logs),
                    "logs": logs,
                    "mock": False
                }, indent=2)
            )]

        except Exception as e:
            logger.error(f"Error querying Splunk: {e}", exc_info=True)
            return await self._mock_query_logs(host, time_range, search_query)

    async def search_recent(self, args: dict) -> Sequence[TextContent]:
        """Search recent events across all indexes via REST API using Basic Auth"""
        search_term = args.get("search_term")
        time_range = args.get("time_range", "15m")
        max_results = args.get("max_results", 100)

        if USE_MOCK or not self.has_userpass:
            return await self._mock_search_recent(search_term)

        try:
            spl_query = f"search {search_term}"

            search_url = f"{SPLUNK_HOST}/services/search/jobs"

            response = requests.post(
                search_url,
                auth=self._get_auth(),
                data={
                    "search": spl_query,
                    "earliest_time": f"-{time_range}" if not time_range.startswith("-") else time_range,
                    "latest_time": "now",
                    "output_mode": "json",
                },
                verify=SPLUNK_VERIFY_SSL,
            )
           

            if response.status_code not in [200, 201]:
                logger.error(f"Search job creation failed: {response.status_code} - {response.text}")
                return await self._mock_search_recent(search_term)

            job_id = response.json().get("sid")
            if not job_id:
                logger.error(f"No job ID returned: {response.text}")
                return await self._mock_search_recent(search_term)

            
            await asyncio.sleep(2)

            results_url = f"{SPLUNK_HOST}/services/search/jobs/{job_id}/results"
            results_response = requests.get(
                results_url,
                auth=self._get_auth(),
                params={"output_mode": "json", "count": max_results},
                verify=SPLUNK_VERIFY_SSL,
            )

            try:
                json_data = results_response.json()
            except ValueError:
                json_data = {"error": results_response.text}

            
            if results_response.status_code != 200:
                logger.error(f"Failed to fetch results: {results_response.status_code} - {results_response.text}")
                return await self._mock_search_recent(search_term)

            results = json_data.get("results", [])

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "search_term": search_term,
                            "results_count": len(results),
                            "results": results[:max_results],
                            "mock": False,
                        },
                        indent=2,
                    ),
                )
            ]

        except Exception as e:
            logger.error(f"Error searching Splunk: {e}", exc_info=True)
            return await self._mock_search_recent(search_term)


    async def send_event(self, args: dict) -> Sequence[TextContent]:
        """Send event to Splunk HEC using token"""
        event = args.get("event")
        sourcetype = args.get("sourcetype", "aitta:test")
        host = args.get("host", "aitta-agent")

        if USE_MOCK or not self.has_token:
            return [TextContent(
                type="text",
                text=json.dumps({"status": "mock", "message": "Event would be sent to HEC"}, indent=2)
            )]

        try:
            hec_url = f"{SPLUNK_HEC_URL}/services/collector/event"
            payload = {
                "event": event,
                "sourcetype": sourcetype,
                "source": "aitta",
                "host": host,
                "time": int(datetime.now().timestamp())
            }

            response = requests.post(
                hec_url,
                headers={
                    "Authorization": f"Splunk {SPLUNK_TOKEN}",
                    "Content-Type": "application/json"
                },
                json=payload,
                verify=SPLUNK_VERIFY_SSL,
                timeout=10
            )

            if response.status_code == 200:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "success",
                        "message": "Event sent to Splunk HEC",
                        "response": response.json(),
                        "event": event
                    }, indent=2)
                )]
            else:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "error",
                        "message": f"HEC returned {response.status_code}",
                        "error": response.text
                    }, indent=2)
                )]

        except Exception as e:
            logger.error(f"Error sending to HEC: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=json.dumps({"status": "error", "message": str(e)}, indent=2)
            )]

    async def _mock_query_logs(self, host: str, time_range: str, search_query: str) -> Sequence[TextContent]:
        """Mock implementation for testing"""
        mock_logs = [
            {
                "timestamp": (datetime.now() - timedelta(minutes=i*3)).isoformat(),
                "level": "ERROR" if i % 3 == 0 else "INFO",
                "message": f"[{host}] Memory usage at {85 + i}%" if i % 3 == 0 else f"[{host}] Normal operation checkpoint {i}",
                "source": "/var/log/app/app.log",
                "sourcetype": "application:log",
                "host": host
            }
            for i in range(15)
        ]

        return [TextContent(
            type="text",
            text=json.dumps({
                "host": host,
                "time_range": time_range,
                "query": search_query,
                "results_count": len(mock_logs),
                "logs": mock_logs,
                "mock": True
            }, indent=2)
        )]

    async def _mock_search_recent(self, search_term: str) -> Sequence[TextContent]:
        """Mock search results"""
        return [TextContent(
            type="text",
            text=json.dumps({
                "search_term": search_term,
                "results_count": 5,
                "results": [{"_time": datetime.now().isoformat(), "_raw": f"Mock result for {search_term}"}],
                "mock": True
            }, indent=2)
        )]

    async def get_alert_details(self, args: dict) -> Sequence[TextContent]:
        """Get alert details (mock)"""
        alert_id = args.get("alert_id")
        alert_details = {
            "alert_id": alert_id,
            "title": "High CPU Usage on Production Server",
            "severity": "High",
            "triggered_at": datetime.now().isoformat(),
            "host": "prod-web-03",
            "metric": "cpu_usage",
            "threshold": 95,
            "current_value": 98.5,
            "description": "CPU utilization has exceeded 95% for 15 minutes"
        }
        return [TextContent(type="text", text=json.dumps(alert_details, indent=2))]

    async def search_errors(self, args: dict) -> Sequence[TextContent]:
        """Search for error patterns using query_logs"""
        host = args.get("host")
        error_pattern = args.get("error_pattern")
        time_range = args.get("time_range", "1h")

        return await self.query_logs({
            "host": host,
            "time_range": time_range,
            "search_query": f'error OR exception OR "{error_pattern}"'
        })

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

def main():
    server = SplunkMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()