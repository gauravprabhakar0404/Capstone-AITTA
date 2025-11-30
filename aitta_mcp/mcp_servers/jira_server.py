"""
Production Jira MCP Server - TOKEN ONLY Authentication
Jira Server/Data Center: http://localhost:8090
Uses JIRA_TOKEN for all operations (Personal Access Token)
"""

import asyncio
import json
from dotenv import load_dotenv
import os
import logging
from datetime import datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from typing import Any, Sequence
import requests

load_dotenv() 
# Configuration - TOKEN ONLY
JIRA_URL = os.getenv("JIRA_URL", "http://localhost:8090")
JIRA_TOKEN = os.getenv("JIRA_TOKEN", "")  # Required - Personal Access Token
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "KAG")
USE_MOCK = os.getenv("USE_MOCK_JIRA", "false").lower() == "true"

# Logging
logging.basicConfig(level=logging.DEBUG)


class JiraMCPServer:
    def __init__(self):
        self.server = Server("jira-server")
        self.has_token = bool(JIRA_TOKEN)     
        self.logger = logging.getLogger(__name__)
        self.setup_tools()
        
        if not self.has_token:
            self.logger.warning("No Jira token provided, using mock mode")
            self.logger.warning("Set JIRA_TOKEN in .env file")
            self.logger.info("For Jira Server/Data Center: Generate Personal Access Token")
            self.logger.info("  Go to: Profile (top right) > Personal Access Tokens > Create token")
        else:
            self.logger.info(f"Jira MCP Server initialized - URL: {JIRA_URL}")
            self.logger.info(f"Using token authentication: {JIRA_TOKEN[:10]}...{JIRA_TOKEN[-5:]}")
            self.logger.info(f"Default project: {JIRA_PROJECT_KEY}")
    
    def _get_headers(self):
        """Get authentication headers for Jira API"""
        return {
            "Authorization": f"Bearer {JIRA_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def setup_tools(self):
        """Register available tools"""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="create_ticket",
                    description="Create a new Jira ticket/issue using token authentication",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project key (e.g., TEST, OPS)", "default": JIRA_PROJECT_KEY},
                            "summary": {"type": "string", "description": "Ticket summary/title"},
                            "description": {"type": "string", "description": "Detailed description"},
                            "priority": {"type": "string", "description": "Priority: Critical, High, Medium, Low", "default": "Medium"},
                            "assignee": {"type": "string", "description": "Username to assign to (leave empty for unassigned)"},
                            "issue_type": {"type": "string", "description": "Issue type (Bug, Task, Story)", "default": "Task"}
                        },
                        "required": ["summary", "description"]
                    }
                ),
                Tool(
                    name="update_ticket",
                    description="Update an existing Jira ticket",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "Jira ticket ID (e.g., TEST-123)"},
                            "comment": {"type": "string", "description": "Comment to add"},
                            "status": {"type": "string", "description": "New status (e.g., In Progress, Done)"},
                            "assignee": {"type": "string", "description": "New assignee username"}
                        },
                        "required": ["ticket_id"]
                    }
                ),
                Tool(
                    name="get_ticket",
                    description="Get details of a Jira ticket",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "Jira ticket ID (e.g., TEST-123)"}
                        },
                        "required": ["ticket_id"]
                    }
                ),
                Tool(
                    name="search_tickets",
                    description="Search for Jira tickets using JQL",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "jql": {"type": "string", "description": "JQL query string (e.g., 'project=TEST AND status=Open')"},
                            "max_results": {"type": "integer", "default": 50}
                        },
                        "required": ["jql"]
                    }
                ),
                Tool(
                    name="get_projects",
                    description="List all available Jira projects",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_issue_types",
                    description="Get available issue types for a project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project key", "default": JIRA_PROJECT_KEY}
                        }
                    }
                ),
                Tool(
                    name="get_current_user",
                    description="Get information about the current authenticated user",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
            if name == "create_ticket":
                return await self.create_ticket(arguments)
            elif name == "update_ticket":
                return await self.update_ticket(arguments)
            elif name == "get_ticket":
                return await self.get_ticket(arguments)
            elif name == "search_tickets":
                return await self.search_tickets(arguments)
            elif name == "get_projects":
                return await self.get_projects(arguments)
            elif name == "get_issue_types":
                return await self.get_issue_types(arguments)
            elif name == "get_current_user":
                return await self.get_current_user(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
    
    async def get_current_user(self, args: dict) -> Sequence[TextContent]:
        """Get current authenticated user info"""
        if USE_MOCK or not self.has_token:
            return [TextContent(
                type="text",
                text=json.dumps({"username": "admin", "displayName": "Admin User", "mock": True}, indent=2)
            )]
        
        try:
            response = requests.get(
                f"{JIRA_URL}/rest/api/2/myself",
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                self.logger.info(f"✓ Authenticated as: {user_data.get('displayName', 'Unknown')}")
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "username": user_data.get("name", ""),
                        "displayName": user_data.get("displayName", ""),
                        "emailAddress": user_data.get("emailAddress", ""),
                        "mock": False
                    }, indent=2)
                )]
            else:
                self.logger.error(f"Failed to get user info: {response.status_code}")
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"Authentication failed: {response.status_code}"}, indent=2)
                )]
                
        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]
    
    async def create_ticket(self, args: dict) -> Sequence[TextContent]:
        """Create a new Jira ticket using token authentication"""
        project = args.get("project", JIRA_PROJECT_KEY)
        summary = args.get("summary")
        description = args.get("description")
        priority = args.get("priority", "Medium")
        assignee = args.get("assignee")
        issue_type = args.get("issue_type", "Task")
        if USE_MOCK or not self.has_token:
            return await self._mock_create_ticket(project, summary, priority)
        
        try:
            # Priority mapping for Jira
            priority_map = {
                "Critical": "Highest",
                "High": "High",
                "Medium": "Medium",
                "Low": "Low"
            }
            
            jira_priority = priority_map.get(priority, "Medium")            
            
            # Jira Server format (plain text description)
            issue_data = {
                "fields": {
                    "project": {"key": project},
                    "summary": summary,
                    "description": description,
                    "issuetype": {"name": issue_type},
                    "priority": {"name": jira_priority}
                }
            }
            
            # Add assignee if provided
            # if assignee:
            #     issue_data["fields"]["assignee"] = {"name": assignee}
            
            self.logger.info(f"Creating Jira ticket in project {project}")
            self.logger.debug(f"Payload: {json.dumps(issue_data, indent=2)}")
            
            # Create the issue using token authentication
            response = requests.post(
                f"{JIRA_URL}/rest/api/2/issue",
                headers=self._get_headers(),
                json=issue_data,
                timeout=30
            )
            
            self.logger.info(f"Jira API response: {response.status_code}")
            
            if response.status_code == 201:
                result = response.json()
                ticket_id = result["key"]
                
                self.logger.info(f"✓ Ticket created successfully: {ticket_id}")
                
                result_data = {
                    "status": "created",
                    "ticket_id": ticket_id,
                    "project": project,
                    "summary": summary,
                    "priority": priority,
                    "assignee": assignee or "Unassigned",
                    "url": f"{JIRA_URL}/browse/{ticket_id}",
                    "created_at": datetime.now().isoformat(),
                    "mock": False
                }
            else:
                error_msg = response.text
                self.logger.error(f"✗ Jira ticket creation failed: {response.status_code} - {error_msg}")
               
                # Try to parse error details
                try:
                    error_details = response.json()
                    self.logger.error(f"Error details: {json.dumps(error_details, indent=2)}")
                    
                    # Check for common errors
                    if "errors" in error_details:
                        for field, message in error_details["errors"].items():
                            self.logger.error(f"  Field '{field}': {message}")
                except:
                     pass                
                return [TextContent(type="text", text="Jira ticket creation failed, falling back to mock response.")]
            
            return [TextContent(type="text", text=json.dumps(result_data, indent=2))]
            
        except Exception as e:
            self.logger.error(f"Exception creating Jira ticket: {e}", exc_info=True)
        
            return await self._mock_create_ticket(project, summary, priority, assignee)
    
    async def _mock_create_ticket(self, project: str, summary: str, priority: str, assignee: str) -> Sequence[TextContent]:
        """Mock ticket creation"""
        ticket_id = f"{project}-{datetime.now().strftime('%H%M%S')}"
        
        self.logger.info(f"Using mock mode - would create ticket: {ticket_id}")
        
        result = {
            "status": "created",
            "ticket_id": ticket_id,
            "project": project,
            "summary": summary,
            "priority": priority,
            "assignee": assignee or "Unassigned",
            "url": f"{JIRA_URL}/browse/{ticket_id}",
            "created_at": datetime.now().isoformat(),
            "mock": True
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    async def get_projects(self, args: dict) -> Sequence[TextContent]:
        """List all available projects"""
        if USE_MOCK or not self.has_token:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "projects": [
                        {"key": "TEST", "name": "Test Project"},
                        {"key": "OPS", "name": "Operations"}
                    ],
                    "mock": True
                }, indent=2)
            )]
        
        try:
            response = requests.get(
                f"{JIRA_URL}/rest/api/2/project",
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                projects = response.json()
                project_list = [
                    {"key": p["key"], "name": p["name"]}
                    for p in projects
                ]
                
                self.logger.info(f"✓ Retrieved {len(project_list)} projects")
                
                return [TextContent(
                    type="text",
                    text=json.dumps({"projects": project_list, "mock": False}, indent=2)
                )]
            else:
                self.logger.error(f"Failed to get projects: {response.status_code}")
                return [TextContent(type="text", text=json.dumps({"error": "Failed to fetch projects"}, indent=2))]
                
        except Exception as e:
            self.logger.error(f"Error getting projects: {e}")
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
    
    async def get_issue_types(self, args: dict) -> Sequence[TextContent]:
        """Get available issue types"""
        project = args.get("project", JIRA_PROJECT_KEY)
        
        if USE_MOCK or not self.has_token:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "issue_types": ["Bug", "Task", "Story", "Epic"],
                    "mock": True
                }, indent=2)
            )]
        
        try:
            response = requests.get(
                f"{JIRA_URL}/rest/api/2/project/{project}",
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                project_data = response.json()
                issue_types = [it["name"] for it in project_data.get("issueTypes", [])]
                
                self.logger.info(f"✓ Retrieved {len(issue_types)} issue types for {project}")
                
                return [TextContent(
                    type="text",
                    text=json.dumps({"issue_types": issue_types, "project": project, "mock": False}, indent=2)
                )]
            else:
                self.logger.error(f"Failed to get issue types: {response.status_code}")
                return [TextContent(type="text", text=json.dumps({"error": "Failed to fetch issue types"}, indent=2))]
                
        except Exception as e:
            self.logger.error(f"Error getting issue types: {e}")
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
    
    async def update_ticket(self, args: dict) -> Sequence[TextContent]:
        """Update an existing ticket"""
        ticket_id = args.get("ticket_id")
        comment = args.get("comment")
        status = args.get("status")
        assignee = args.get("assignee")
        
        if USE_MOCK or not self.has_token:
            updates = []
            if comment:
                updates.append(f"Added comment")
            if status:
                updates.append(f"Changed status to: {status}")
            if assignee:
                updates.append(f"Assigned to: {assignee}")
            
            result = {
                "status": "updated",
                "ticket_id": ticket_id,
                "updates": updates,
                "updated_at": datetime.now().isoformat(),
                "mock": True
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        try:
            updates = []
            
            # Add comment
            if comment:
                comment_response = requests.post(
                    f"{JIRA_URL}/rest/api/2/issue/{ticket_id}/comment",
                    headers=self._get_headers(),
                    json={"body": comment},
                    timeout=10
                )
                if comment_response.status_code == 201:
                    updates.append("Added comment")
                    self.logger.info(f"✓ Comment added to {ticket_id}")
            
            # Update assignee
            if assignee:
                assignee_response = requests.put(
                    f"{JIRA_URL}/rest/api/2/issue/{ticket_id}",
                    headers=self._get_headers(),
                    json={"fields": {"assignee": {"name": assignee}}},
                    timeout=10
                )
                if assignee_response.status_code == 204:
                    updates.append(f"Assigned to: {assignee}")
                    self.logger.info(f"✓ Ticket {ticket_id} assigned to {assignee}")
            
            # Update status (transition)
            if status:
                # Get available transitions
                transitions_response = requests.get(
                    f"{JIRA_URL}/rest/api/2/issue/{ticket_id}/transitions",
                    headers=self._get_headers(),
                    timeout=10
                )
                
                if transitions_response.status_code == 200:
                    transitions = transitions_response.json()["transitions"]
                    # Find matching transition
                    for transition in transitions:
                        if transition["name"].lower() == status.lower() or transition["to"]["name"].lower() == status.lower():
                            # Execute transition
                            transition_response = requests.post(
                                f"{JIRA_URL}/rest/api/2/issue/{ticket_id}/transitions",
                                headers=self._get_headers(),
                                json={"transition": {"id": transition["id"]}},
                                timeout=10
                            )
                            if transition_response.status_code == 204:
                                updates.append(f"Changed status to: {status}")
                                self.logger.info(f"✓ Status changed to {status} for {ticket_id}")
                            break
            
            result = {
                "status": "updated",
                "ticket_id": ticket_id,
                "updates": updates,
                "updated_at": datetime.now().isoformat(),
                "mock": False
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            self.logger.error(f"Error updating Jira ticket: {e}")
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
    
    async def get_ticket(self, args: dict) -> Sequence[TextContent]:
        """Get ticket details"""
        ticket_id = args.get("ticket_id")
        
        if USE_MOCK or not self.has_token:
            ticket_details = {
                "ticket_id": ticket_id,
                "summary": "Memory Leak Detected on prod-web-03",
                "status": "Open",
                "priority": "High",
                "assignee": "DevOps Team",
                "created": datetime.now().isoformat(),
                "description": "Automated incident detected by AITTA agent",
                "mock": True
            }
            return [TextContent(type="text", text=json.dumps(ticket_details, indent=2))]
        
        try:
            response = requests.get(
                f"{JIRA_URL}/rest/api/2/issue/{ticket_id}",
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                issue = response.json()
                fields = issue["fields"]
                
                ticket_details = {
                    "ticket_id": ticket_id,
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", ""),
                    "priority": fields.get("priority", {}).get("name", ""),
                    "assignee": fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned",
                    "created": fields.get("created", ""),
                    "description": fields.get("description", ""),
                    "url": f"{JIRA_URL}/browse/{ticket_id}",
                    "mock": False
                }
                
                self.logger.info(f"✓ Retrieved ticket {ticket_id}")
            else:
                ticket_details = {"error": f"Ticket not found: {response.status_code}"}
                self.logger.error(f"Failed to get ticket {ticket_id}: {response.status_code}")
            
            return [TextContent(type="text", text=json.dumps(ticket_details, indent=2))]
            
        except Exception as e:
            self.logger.error(f"Error fetching Jira ticket: {e}")
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
    
    async def search_tickets(self, args: dict) -> Sequence[TextContent]:
        """Search tickets using JQL"""
        jql = args.get("jql")
        max_results = args.get("max_results", 50)
        
        if USE_MOCK or not self.has_token:
            results = {
                "jql": jql,
                "total": 5,
                "issues": [
                    {
                        "key": f"{JIRA_PROJECT_KEY}-{100 + i}",
                        "summary": f"Sample incident {i}",
                        "status": "Open" if i % 2 == 0 else "Resolved",
                        "priority": "High"
                    }
                    for i in range(5)
                ],
                "mock": True
            }
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        try:
            response = requests.get(
                f"{JIRA_URL}/rest/api/2/search",
                headers=self._get_headers(),
                params={"jql": jql, "maxResults": max_results},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = {
                    "jql": jql,
                    "total": data.get("total", 0),
                    "issues": [
                        {
                            "key": issue["key"],
                            "summary": issue["fields"].get("summary", ""),
                            "status": issue["fields"].get("status", {}).get("name", ""),
                            "priority": issue["fields"].get("priority", {}).get("name", "")
                        }
                        for issue in data.get("issues", [])
                    ],
                    "mock": False
                }
                
                self.logger.info(f"✓ Search returned {len(results['issues'])} results")
            else:
                results = {"error": f"Search failed: {response.status_code}"}
                self.logger.error(f"Search failed: {response.status_code}")
            
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
            
        except Exception as e:
            self.logger.error(f"Error searching Jira: {e}")
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
    
    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

def main():
    server = JiraMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()