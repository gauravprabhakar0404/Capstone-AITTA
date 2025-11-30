"""
Production CMDB (Configuration Management Database) MCP Server
Provides tools to query asset information, ownership, dependencies, and create incidents
"""

import asyncio
import json
from dotenv import load_dotenv
import os
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from typing import Any, Sequence, Optional
import aiohttp

load_dotenv()

# Configuration
CMDB_API_URL = os.getenv("CMDB_API_URL", "").rstrip("/")
CMDB_USERNAME = os.getenv("CMDB_USERNAME", "")
CMDB_PASSWORD = os.getenv("CMDB_PASSWORD", "")
USE_MOCK_CMDB = os.getenv("USE_MOCK_CMDB", "true").lower() == "true"

# HTTP defaults for ServiceNow
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=60)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CMDBMCPServer:
    def __init__(self):
        self.server = Server("cmdb-server")
        self.setup_tools()

        # Mock CMDB database
        self.cmdb_data = {
            "prod-web-01": {
                "hostname": "prod-web-01",
                "ip": "10.0.1.10",
                "service": "Payment Gateway",
                "owner_team": "Payment Team",
                "environment": "Production",
                "location": "US-East-1",
                "dependencies": ["prod-db-01", "prod-cache-01"],
                "criticality": "High",
                "incident_history": [
                    {"date": "2024-10-15", "type": "Memory Leak", "duration": "2h"},
                    {"date": "2024-09-20", "type": "Disk Space", "duration": "1h"},
                ],
            },
            "prod-web-02": {
                "hostname": "prod-web-02",
                "ip": "10.0.1.11",
                "service": "Order Service",
                "owner_team": "Order Team",
                "environment": "Production",
                "location": "US-West-2",
                "dependencies": ["prod-db-02", "prod-mq-01"],
                "criticality": "Critical",
                "incident_history": [],
            },
            "prod-web-03": {
                "hostname": "prod-web-03",
                "ip": "10.0.1.12",
                "service": "Payment Gateway",
                "owner_team": "Payment Team",
                "environment": "Production",
                "location": "US-East-1",
                "dependencies": ["prod-db-01", "prod-cache-01"],
                "criticality": "High",
                "incident_history": [
                    {"date": "2024-11-01", "type": "High CPU", "duration": "3h"}
                ],
            },
        }


    def _session(self) -> aiohttp.ClientSession:
        auth = aiohttp.BasicAuth(CMDB_USERNAME, CMDB_PASSWORD) if CMDB_USERNAME or CMDB_PASSWORD else None
        return aiohttp.ClientSession(auth=auth, timeout=HTTP_TIMEOUT, headers=HEADERS)

    async def _sn_get(self, path: str, params: Optional[dict] = None) -> dict:
        if not CMDB_API_URL:
            raise RuntimeError("CMDB_API_URL is not set")        
                
        async with self._session() as session:
            url = f"{CMDB_API_URL}{path}"
            async with session.get(url, params=params) as r:
                try:
                    text = await r.text()                 
                    if r.status >= 400:
                        raise RuntimeError(f"GET {url} failed {r.status}: {text}")
                    return json.loads(text)
                except Exception as e:
                    raise RuntimeError(f"Error parsing JSON from {url}: {e}")

    async def _sn_post(self, path: str, payload: dict) -> dict:
        if not CMDB_API_URL:
            raise RuntimeError("CMDB_API_URL is not set")
        async with self._session() as session:
            url = f"{CMDB_API_URL}{path}"
            async with session.post(url, json=payload) as r:
                text = await r.text()
                if r.status >= 400:
                    raise RuntimeError(f"POST {url} failed {r.status}: {text}")
                return json.loads(text)

   

    def setup_tools(self):
        """Register available tools"""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="get_asset_info",
                    description="Get complete information about an asset/server",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hostname": {
                                "type": "string",
                                "description": "Hostname of the asset",
                            }
                        },
                        "required": ["hostname"],
                    },
                ),
                Tool(
                    name="get_owner_team",
                    description="Get the team that owns a specific asset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hostname": {
                                "type": "string",
                                "description": "Hostname of the asset",
                            }
                        },
                        "required": ["hostname"],
                    },
                ),
                Tool(
                    name="get_dependencies",
                    description="Get service dependencies for an asset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hostname": {
                                "type": "string",
                                "description": "Hostname of the asset",
                            }
                        },
                        "required": ["hostname"],
                    },
                ),
                Tool(
                    name="get_incident_history",
                    description="Get past incident history for an asset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hostname": {
                                "type": "string",
                                "description": "Hostname of the asset",
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back",
                                "default": 30,
                            },
                        },
                        "required": ["hostname"],
                    },
                ),
                Tool(
                    name="search_by_service",
                    description="Find all assets associated with a service",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "Service name to search for",
                            }
                        },
                        "required": ["service_name"],
                    },
                ),
                Tool(
                    name="create_incident",
                    description="Create a new incident in ServiceNow (links CI if found)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hostname": {"type": "string"},
                            "short_description": {"type": "string"},
                            "description": {"type": "string"},
                            "urgency": {"type": "string", "enum": ["1", "2", "3"]},
                            "impact": {"type": "string", "enum": ["1", "2", "3"]},
                        },
                        "required": ["hostname", "short_description"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
            try:
                if name == "get_asset_info":
                    return await self.get_asset_info(arguments)
                elif name == "get_owner_team":
                    return await self.get_owner_team(arguments)
                elif name == "get_dependencies":
                    return await self.get_dependencies(arguments)
                elif name == "get_incident_history":
                    return await self.get_incident_history(arguments)
                elif name == "search_by_service":
                    return await self.search_by_service(arguments)
                elif name == "create_incident":
                    return await self.create_incident(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Tool {name} failed: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}))]



    async def get_asset_info(self, args: dict) -> Sequence[TextContent]:
        try:
            hostname = args.get("hostname")
            if not hostname:
                return [TextContent(type="text", text=json.dumps({"error": "hostname is required"}))]

            # MOCK path
            if USE_MOCK_CMDB:
                asset = self.cmdb_data.get(hostname)
                if not asset:
                    asset = {
                        "hostname": hostname,
                        "service": "Unknown",
                        "owner_team": "DevOps",
                        "environment": "Production",
                        "dependencies": [],
                        "criticality": "Medium",
                        "status": "Not found in CMDB",
                        "incident_history": [],
                    }
                return [TextContent(type="text", text=json.dumps(asset, indent=2))]
            
            # ServiceNow path
            data = await self._sn_get("/api/now/table/cmdb_ci_server", {"name": hostname, "sysparm_limit": "1","sysparm_display_value": "true"})
            
            rows = data.get("result", [])
            if not rows:
                asset = {"hostname": hostname, "status": "Not found"}
            else:
                ci = rows[0]               
                    
                asset = {
                            "hostname": ci.get("name"),
                            "ip": ci.get("ip_address"),
                            "owner_team": ci.get("u_owner_team") or ci.get("managed_by_group", {}).get("display_value") or ci.get("owned_by") or "Unassigned",
                            "environment": ci.get("u_environment") or ci.get("classification") or "Production",
                            "location": ci.get("location", {}).get("display_value") if isinstance(ci.get("location"), dict) else ci.get("location"),
                            "criticality": ci.get("u_criticality") or "Medium",
                            "status": ci.get("operational_status") or "Unknown",
                            "os_domain": ci.get("os_domain"),
                            "os_version": ci.get("os_version"),
                            "internet_facing": ci.get("internet_facing") == "true",
                            "virtual": ci.get("virtual") == "true",
                            "serial_number": ci.get("serial_number"),
                            "asset_tag": ci.get("asset_tag"),
                            "disk_space": ci.get("disk_space"),
                            "ram": ci.get("ram"),
                            "manufacturer": ci.get("manufacturer"),
                            "model": ci.get("model_id", {}).get("display_value") if isinstance(ci.get("model_id"), dict) else ci.get("model_id"),
                            "support_group": ci.get("support_group"),
                            "assignment_group": ci.get("assignment_group"),
                            "managed_by_group": ci.get("managed_by_group", {}).get("display_value") if isinstance(ci.get("managed_by_group"), dict) else ci.get("managed_by_group"),
                            "location_region": ci.get("location", {}).get("display_value") if isinstance(ci.get("location"), dict) else None,
                            "created_on": ci.get("sys_created_on"),
                            "updated_on": ci.get("sys_updated_on"),
                            "attestation_status": ci.get("attestation_status"),
                            "fault_count": ci.get("fault_count"),
                            "service": (  ci.get("business_service", {}).get("display_value")  if isinstance(ci.get("business_service"), dict)
                                        else ci.get("business_service")
                                    )
                                    or (
                                        ci.get("service_offering", {}).get("display_value")
                                        if isinstance(ci.get("service_offering"), dict)
                                        else ci.get("service_offering")
                                    )
                                    or ci.get("u_service")
                                    or "Unknown",
                        }  
            return [TextContent(type="text", text=json.dumps(asset, indent=2))]
        except Exception as e:
            logger.error(f"asset: {e}")            
            return [TextContent(type="text", text=json.dumps({"error": "Error retrieving asset info"}))]
        
    def safe_display(self,ci, field):
        val = ci.get(field)
        if isinstance(val, dict):
            return val.get("display_value")
        return val  # if it's already a string or None

    async def get_owner_team(self, args: dict) -> Sequence[TextContent]:
        hostname = args.get("hostname")
        if not hostname:
            return [TextContent(type="text", text=json.dumps({"error": "hostname is required"}))]

        # MOCK path
        if USE_MOCK_CMDB:
            asset = self.cmdb_data.get(hostname, {})
            result = {
                "hostname": hostname,
                "owner_team": asset.get("owner_team", "DevOps"),
                "service": asset.get("service", "Unknown"),
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # ServiceNow path
        data = await self._sn_get("/api/now/table/cmdb_ci_server", {"name": hostname, "sysparm_limit": "1"})
        rows = data.get("result", [])
        owner_team = rows[0].get("u_owner_team") if rows else "Unassigned"
        result = {"hostname": hostname, "owner_team": owner_team}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def get_dependencies(self, args: dict) -> Sequence[TextContent]:
        hostname = args.get("hostname")
        if not hostname:
            return [TextContent(type="text", text=json.dumps({"error": "hostname is required"}))]

        # MOCK path
        if USE_MOCK_CMDB:
            asset = self.cmdb_data.get(hostname, {})
            dependencies = asset.get("dependencies", [])
            dependency_details = []
            for dep in dependencies:
                dep_asset = self.cmdb_data.get(dep, {})
                dependency_details.append(
                    {
                        "hostname": dep,
                        "service": dep_asset.get("service", "Unknown"),
                        "criticality": dep_asset.get("criticality", "Unknown"),
                    }
                )
            result = {
                "hostname": hostname,
                "total_dependencies": len(dependencies),
                "dependencies": dependency_details,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # ServiceNow path
        srv = await self._sn_get("/api/now/table/cmdb_ci_server", {"name": hostname, "sysparm_limit": "1"})
        rows = srv.get("result", [])
        if not rows:
            return [TextContent(type="text", text=json.dumps({"error": "CI not found"}))]
        ci = rows[0]
        rel = await self._sn_get("/api/now/table/cmdb_rel_ci", {"child": ci.get("sys_id"), "sysparm_fields": "parent"})
        parents = [row["parent"] for row in rel.get("result", []) if row.get("parent")]
        result = {
            "hostname": hostname,
            "total_dependencies": len(parents),
            "dependencies": parents,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def get_incident_history(self, args: dict) -> Sequence[TextContent]:
        hostname = args.get("hostname")
        days = args.get("days", 30)

        # For now, history stays mock whether using ServiceNow or not
        asset = self.cmdb_data.get(hostname, {})
        history = asset.get("incident_history", [])
        result = {
            "hostname": hostname,
            "period_days": days,
            "total_incidents": len(history),
            "incidents": history,
            "patterns": self._analyze_patterns(history),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    def _analyze_patterns(self, history: list) -> dict:
        if not history:
            return {"recurring": False, "common_type": None}
        types = [inc["type"] for inc in history]
        most_common = max(set(types), key=types.count) if types else None
        return {
            "recurring": len(history) > 2,
            "common_type": most_common,
            "frequency": f"{len(history)} incidents",
        }

    async def search_by_service(self, args: dict) -> Sequence[TextContent]:
        service_name = args.get("service_name", "").strip()
        if not service_name:
            return [TextContent(type="text", text=json.dumps({"error": "service_name is required"}))]

        # MOCK-only search (simple contains)
        matching_assets = [
            {
                "hostname": host,
                "owner_team": data["owner_team"],
                "environment": data["environment"],
                "criticality": data["criticality"],
            }
            for host, data in self.cmdb_data.items()
            if service_name.lower() in data["service"].lower()
        ]
        return [TextContent(type="text", text=json.dumps(matching_assets, indent=2))]

    async def create_incident(self, args: dict) -> Sequence[TextContent]:
        hostname = args.get("hostname")
        short_desc = args.get("short_description")
        desc = args.get("description", f"Incident for {hostname}")
        urgency = args.get("urgency", "3")
        impact = args.get("impact", "3")

        if not short_desc or not hostname:
            return [TextContent(type="text", text=json.dumps({"error": "hostname and short_description are required"}))]

        # MOCK path
        if USE_MOCK_CMDB:
            inc = {"incident_number": "MOCK12345", "sys_id": "mock-sysid"}            
            return [TextContent(type="text", text=json.dumps(inc, indent=2))]

        try:
            # Resolve CI sys_id
            srv = await self._sn_get("/api/now/table/cmdb_ci_server", {"name": hostname, "sysparm_limit": "1"})
            ci_row = srv.get("result", [{}])[0]
            ci_sys_id = ci_row.get("sys_id")

            payload = {
                "short_description": short_desc,
                "description": desc,
                "urgency": urgency,
                "impact": impact,
            }
            if ci_sys_id:
                payload["cmdb_ci"] = ci_sys_id

            result = await self._sn_post("/api/now/table/incident", payload)
            inc = result.get("result", {})
            out = {"incident_number": inc.get("number"), "sys_id": inc.get("sys_id")}
            return [TextContent(type="text", text=json.dumps(out, indent=2))]
        except Exception as e:
            logger.error(f"Error creating incident: {e}")            
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    # ---------------- Run loop (matches your working sample) ----------------

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

def main():
    
    server = CMDBMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()