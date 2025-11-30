"""
Agent core logic for AITTA
Contains the AITTAgent class that orchestrates incident triage and ticket creation
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

import google.generativeai as genai
from fastapi import HTTPException
from sqlalchemy.orm import Session

from config.config import Config
from models.database import AgentActivityRecord, TicketRecord
from models.schemas import AlertData, TicketResponse
from aitta_mcp.mcp_client_manager import MCPClientManager

# Global MCP manager
mcp_manager = MCPClientManager(Config)


class AITTAgent:
    """The Agentic AI core that orchestrates the triage process"""

    def __init__(self, db: Session, config: Config = None):
        self.db = db
        self.config = config
        self._setup_llm()

    def _setup_llm(self):
        """Initialize LLM based on configuration"""
        if self.config.LLM_PROVIDER == "gemini" and self.config.GEMINI_API_KEY:
            genai.configure(api_key=self.config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            self.llm_available = True
        elif self.config.LLM_PROVIDER == "claude" and self.config.ANTHROPIC_API_KEY:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.config.ANTHROPIC_API_KEY)
            self.llm_available = True
        else:
            logging.getLogger(__name__).warning("No LLM configured, using rule-based triage")
            self.llm_available = False

    def log_activity(self, alert_id: str, action: str, detail: str, status: str):
        """Log agent activity to database"""
        try:
            activity = AgentActivityRecord(
                alert_id=alert_id,
                action=action,
                detail=detail,
                status=status
            )
            self.db.add(activity)
            self.db.commit()
            logging.getLogger(__name__).info(f"[{alert_id}] {action}: {detail}")
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to log activity: {e}")

    async def process_alert(self, alert: AlertData) -> TicketResponse:
        """
        Main agentic workflow:
        1. Retrieve logs from Splunk
        2. Enrich with CMDB data
        3. Analyze with LLM or rules
        4. Create Jira ticket
        5. Create ServiceNow incident
        6. Save ticket record
        """
        start_time = datetime.now()

        # Step 1: Log alert receipt
        self.log_activity(
            alert.alert_id,
            "Alert Received",
            f"{alert.severity} alert on {alert.host}: {alert.message}",
            "processing",
        )

        # Step 2: Retrieve logs from Splunk
        logs = await self._retrieve_logs(alert)

        # Step 3: Enrich with CMDB data
        cmdb_data = await self._enrich_with_cmdb(alert, logs)

        # Step 4: Analyze and determine priority
        analysis = await self._analyze_incident(alert, logs, cmdb_data)

        # Step 5: Create Jira ticket
        ticket = await self._create_jira_ticket(alert, analysis)

        # Step 6: Create ServiceNow incident
        await self._create_servicenow_incident(alert, analysis)

        # Step 7: Save ticket record
        self._save_ticket_record(alert, analysis, ticket, start_time)

        return ticket

    async def _retrieve_logs(self, alert: AlertData) -> List[Dict]:
        """Retrieve relevant logs from Splunk"""
        logs = []
        try:
            logs_result = await asyncio.wait_for(
                mcp_manager.call_tool(
                    "splunk",
                    "query_logs",
                    {
                        "host": f"{alert.host}",
                        "time_range": f"{self.config.AGENT_LOG_TIMERANGE}m",
                        "search_query": "(error OR exception OR failed)",
                    },
                ),
                timeout=20,
            )

            logs_result_obj = self._parse_tool_response(logs_result)
            logs = logs_result_obj.get("logs", [])

            self.log_activity(
                alert.alert_id,
                "Logs Retrieved",
                f"Found {logs_result_obj.get('results_count', len(logs))} relevant log entries from Splunk",
                "complete",
            )

        except Exception as e:
            logging.getLogger(__name__).error(f"Splunk query failed: {type(e).__name__} - {e}")
            logs = []
            self.log_activity(alert.alert_id, "Logs Retrieval", f"Failed: {str(e)}", "error")

        return logs

    async def _enrich_with_cmdb(self, alert: AlertData, logs: List[Dict]) -> Dict[str, Any]:
        """Enrich alert with CMDB data"""
        owner_team = "DevOps"
        service = "DevOps Service"
        cmdb_data = {}

        try:
            cmdb_result = await asyncio.wait_for(
                mcp_manager.call_tool(
                    "cmdb",
                    "get_asset_info",
                    {"hostname": alert.host},
                ),
                timeout=20,
            )
            cmdb_data = self._parse_tool_response(cmdb_result)
            owner_team = cmdb_data.get("owner_team", owner_team)
            service = cmdb_data.get("service", service)

            self.log_activity(
                alert.alert_id,
                "Context Enriched",
                f"Service: {service}, Owner: {owner_team}",
                "complete",
            )

        except Exception as e:
            logging.getLogger(__name__).error(f"CMDB query failed: {type(e).__name__} - {e}")
            self.log_activity(alert.alert_id, "CMDB Query", f"Failed: {str(e)}", "error")

        return cmdb_data

    async def _analyze_incident(self, alert: AlertData, logs: List[Dict], cmdb_data: Dict) -> Dict:
        """Analyze incident and determine priority"""
        try:
            if self.llm_available:
                analysis = await asyncio.wait_for(
                    self._llm_analysis(alert, logs, cmdb_data),
                    timeout=30
                )
            else:
                analysis = self._rule_based_analysis(alert, logs, cmdb_data)

            if not isinstance(analysis, dict):
                raise RuntimeError("Analysis did not return a dict")

            self.log_activity(
                alert.alert_id,
                "Analysis Complete",
                f"Priority: {analysis.get('priority','Unknown')}, Root cause identified",
                "complete",
            )

            return analysis

        except Exception as e:
            logging.getLogger(__name__).error(f"Analysis failed: {type(e).__name__} - {e}")
            # Fallback minimal analysis
            return {
                "priority": alert.severity,
                "summary": f"{alert.severity} alert on {alert.host}",
                "description": alert.message,
            }

    async def _create_jira_ticket(self, alert: AlertData, analysis: Dict) -> TicketResponse:
        """Create Jira ticket"""
        try:
            ticket_result = await asyncio.wait_for(
                mcp_manager.call_tool(
                    "jira",
                    "create_ticket",
                    {
                        "project": self.config.JIRA_PROJECT_KEY,
                        "summary": analysis["summary"],
                        "description": analysis["description"],
                        "priority": analysis["priority"],
                        "assignee": analysis.get("assigned_to", "DevOps"),
                        "issue_type": analysis.get("issue_type", "Task"),
                    },
                ),
                timeout=20,
            )

            ticket_data = self._parse_tool_response(ticket_result)
            ticket_id = ticket_data.get("ticket_id", f"{self.config.JIRA_PROJECT_KEY}-XXXX")
            ticket_url = ticket_data.get("url", "")

            processing_time = (datetime.now() - alert.timestamp.replace(tzinfo=None)).total_seconds()

            self.log_activity(
                alert.alert_id,
                "Ticket Created",
                f"{ticket_id} assigned to {analysis.get('assigned_to', 'DevOps')}",
                "complete",
            )

            return TicketResponse(
                ticket_id=ticket_id,
                priority=analysis["priority"],
                summary=analysis["summary"],
                description=analysis["description"],
                assigned_to=analysis.get("assigned_to", "DevOps"),
                url=ticket_url,
                created_at=datetime.now(),
                processing_time=processing_time,
            )

        except Exception as e:
            logging.getLogger(__name__).error(f"Ticket creation failed: {type(e).__name__} - {e}")
            self.log_activity(alert.alert_id, "Ticket Creation", f"Failed: {str(e)}", "error")
            raise HTTPException(status_code=500, detail=f"Failed to create ticket: {str(e)}")

    async def _create_servicenow_incident(self, alert: AlertData, analysis: Dict):
        """Create ServiceNow incident"""
        try:
            incident_result = await asyncio.wait_for(
                mcp_manager.call_tool(
                    "cmdb",
                    "create_incident",
                    {
                        "hostname": alert.host,
                        "short_description": analysis["summary"],
                        "description": analysis["description"],
                        "urgency": self._map_priority_to_urgency(analysis["priority"]),
                        "impact": self._map_priority_to_impact(analysis["priority"]),
                    },
                ),
                timeout=20,
            )

            incident_data = self._parse_tool_response(incident_result)
            incident_number = incident_data.get("incident_number", "SN-XXXX")

            self.log_activity(
                alert.alert_id,
                "ServiceNow Incident Created",
                f"Incident {incident_number} created in ServiceNow",
                "complete",
            )

        except Exception as e:
            logging.getLogger(__name__).error(f"ServiceNow incident creation failed: {type(e).__name__} - {e}")
            self.log_activity(alert.alert_id, "ServiceNow Incident Creation", f"Failed: {str(e)}", "error")

    def _map_priority_to_urgency(self, priority: str) -> str:
        """Map AITTA priority to ServiceNow urgency"""
        priority_map = {
            "Critical": "1",  # High urgency
            "High": "2",      # Medium urgency
            "Medium": "3",    # Low urgency
            "Low": "3"        # Low urgency
        }
        return priority_map.get(priority, "3")

    def _map_priority_to_impact(self, priority: str) -> str:
        """Map AITTA priority to ServiceNow impact"""
        impact_map = {
            "Critical": "1",  # High impact
            "High": "2",      # Medium impact
            "Medium": "3",    # Low impact
            "Low": "3"        # Low impact
        }
        return impact_map.get(priority, "3")

    def _save_ticket_record(self, alert: AlertData, analysis: Dict, ticket: TicketResponse, start_time: datetime):
        """Save ticket record to database"""
        ticket_record = TicketRecord(
            ticket_id=ticket.ticket_id,
            alert_id=alert.alert_id,
            host=alert.host,
            severity=alert.severity,
            priority=analysis["priority"],
            summary=analysis["summary"],
            description=analysis["description"],
            assigned_to=ticket.assigned_to,
            processing_time=ticket.processing_time,
            status="created",
        )
        self.db.add(ticket_record)
        self.db.commit()

    def _parse_tool_response(self, response) -> Dict:
        """Parse response from MCP tools"""
        if not response:
            raise RuntimeError("Tool returned no content")

        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError as je:
                raise RuntimeError(f"Invalid JSON from tool: {je}")
        elif isinstance(response, dict):
            return response
        else:
            raise RuntimeError(f"Unexpected response type: {type(response)}")

    async def _llm_analysis(self, alert: AlertData, logs: List, cmdb_data: Dict) -> Dict:
        """Use LLM for intelligent analysis"""
        analysis_prompt = f"""You are an expert SRE analyzing an incident alert. Provide your analysis in JSON format.

            Alert Details:
            - Severity: {alert.severity}
            - Host: {alert.host}
            - Message: {alert.message}
            - Timestamp: {alert.timestamp}

            Recent Logs (last {len(logs)} entries):
            {json.dumps(logs[:10], indent=2)}

            Asset Information:
            - Owner Team: {cmdb_data.get('owner_team', 'Unknown')}
            - Service: {cmdb_data.get('service', 'Unknown')}
            - Criticality: {cmdb_data.get('criticality', 'Unknown')}
            - Dependencies: {cmdb_data.get('dependencies', [])}

            Analyze and provide:
            1. Priority (Critical/High/Medium/Low)
            2. Root cause summary
            3. Ticket summary (concise title)
            4. Detailed description for the ticket
            5. The JSON must include a valid Jira issue_type from [Bug, Task, Story, Epic], defaulting to "Task" if unsure.

            Response format (JSON only):
            {{
                "priority": "High",
                "root_cause": "Brief technical summary",
                "summary": "Concise ticket title",
                "description": "Detailed description with timestamps, affected services, and recommended actions",
                "issue_type": "Task"
            }}"""

        try:
            if self.config.LLM_PROVIDER == "gemini":
                response = self.model.generate_content(analysis_prompt)
                analysis_text = response.text.strip()
            else:  # Claude
                message = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": analysis_prompt}]
                )
                analysis_text = message.content[0].text

            # Extract JSON
            if '```json' in analysis_text:
                analysis_text = analysis_text.split('```json')[1].split('```')[0].strip()
            elif '```' in analysis_text:
                analysis_text = analysis_text.split('```')[1].split('```')[0].strip()

            analysis = json.loads(analysis_text)
            return analysis

        except Exception as e:
            logging.getLogger(__name__).error(f"LLM analysis failed: {e}, falling back to rules")
            return self._rule_based_analysis(alert, logs, cmdb_data)

    def _rule_based_analysis(self, alert: AlertData, logs: List, cmdb_data: Dict) -> Dict:
        """Fallback rule-based analysis"""
        # Determine priority based on severity and criticality
        criticality = cmdb_data.get('criticality', 'Medium')

        priority_map = {
            ('Critical', 'High'): 'Critical',
            ('Critical', 'Medium'): 'High',
            ('High', 'High'): 'High',
            ('High', 'Medium'): 'Medium',
            ('Medium', 'High'): 'Medium',
        }

        priority = priority_map.get((alert.severity, criticality), 'Medium')

        # Generate summary
        summary = f"{alert.severity} Alert: {alert.message[:50]} on {alert.host}"

        # Generate description
        error_count = sum(1 for log in logs if 'error' in log.get('message', '').lower())
        description = f"""
        **Alert Details:**
        - Host: {alert.host}
        - Service: {cmdb_data.get('service', 'Unknown')}
        - Severity: {alert.severity}
        - Timestamp: {alert.timestamp}

        **Message:**
        {alert.message}

        **Analysis:**
        - {error_count} error entries found in logs
        - Service criticality: {criticality}
        - Assigned priority: {priority}

        **Recent Log Entries:**
        {chr(10).join([f"- [{log.get('timestamp', 'N/A')}] {log.get('message', 'No message')[:100]}" for log in logs[:5]])}

        **Recommended Actions:**
        1. Investigate the root cause based on log patterns
        2. Check service dependencies: {', '.join(cmdb_data.get('dependencies', []))}
        3. Monitor for recurring patterns
        """

        return {
                    'priority': priority,
                    'root_cause': f'Alert triggered: {alert.message}',
                    'summary': summary,
                    'description': description,
                    'issue_type': 'Task'
                }

    async def scan_and_create_alerts(self, time_range: str = "24h") -> Dict[str, Any]:
        """
        Scan Splunk for recent errors and automatically create alerts for affected hosts
        Returns comprehensive results about the scan and processed alerts
        """
        logger = logging.getLogger(__name__)
        logger.info(f"Scanning Splunk for errors in the last {time_range}")

        try:
            # Step 1: Search Splunk for recent errors across all hosts
            search_result = await asyncio.wait_for(
                mcp_manager.call_tool(
                    "splunk",
                    "search_recent",
                    {
                        "search_term": "index=* (error OR exception OR failed OR fatal OR timeout) | head 1000 | table _time, host, source, _raw",
                        "time_range": "24h",
                        "max_results": 1000
                    }
                ),

                timeout=30,
            )

            # Parse the search results
            search_data = self._parse_tool_response(search_result)
            error_events = search_data.get("results", [])

            # Step 2: Group errors by host and identify unique affected hosts
            affected_hosts = {}
            for event in error_events:
                host = event.get("host", "unknown")
                raw_message = event.get("_raw", "")

                if host not in affected_hosts:
                    affected_hosts[host] = {
                        "host": host,
                        "error_count": 0,
                        "messages": [],
                        "severity": "Medium",  # Default
                        "latest_timestamp": event.get("_time", datetime.now().isoformat())
                    }

                affected_hosts[host]["error_count"] += 1
                affected_hosts[host]["messages"].append(raw_message[:200])  # Limit message length

                # Determine severity based on error patterns
                if any(keyword in raw_message.lower() for keyword in ["critical", "fatal", "panic", "outage"]):
                    affected_hosts[host]["severity"] = "Critical"
                elif any(keyword in raw_message.lower() for keyword in ["high", "severe", "major"]):
                    affected_hosts[host]["severity"] = "High"

            # Step 3: Create alerts for each affected host and process them
            processed_alerts = []

            for host_data in affected_hosts.values():
               
                # Create alert data
                alert_id = f"auto-scan-{host_data['host']}-{int(datetime.now().timestamp())}"

                alert_data = {
                    "alert_id": alert_id,
                    "severity": host_data["severity"],
                    "message": f"Multiple errors detected on {host_data['host']}: {host_data['error_count']} errors in {time_range}. Latest: {host_data['messages'][-1][:100]}...",
                    "host": host_data["host"],
                    "timestamp": datetime.now(),
                    "metadata": {
                        "scan_source": "splunk_auto_scan",
                        "error_count": host_data["error_count"],
                        "time_range": time_range,
                        "error_messages": host_data["messages"][:5]  # Include first 5 error messages
                    }
                }

                try:
                    logger.info(f"Processing auto-generated alert for {host_data['host']}: {alert_id}")

                    # Convert to AlertData model and process
                    alert = AlertData(**alert_data)
                    ticket = await self.process_alert(alert)

                    # Get activity log for this alert
                    from models.database import AgentActivityRecord
                    activities = self.db.query(AgentActivityRecord)\
                        .filter(AgentActivityRecord.alert_id == alert_id)\
                        .order_by(AgentActivityRecord.timestamp.desc())\
                        .limit(5)\
                        .all()

                    activity_log = [
                        {
                            'time': a.timestamp.strftime('%H:%M'),
                            'action': a.action,
                            'detail': a.detail,
                            'status': a.status
                        }
                        for a in activities
                    ]

                    processed_alerts.append({
                        "alert_id": alert_id,
                        "host": host_data["host"],
                        "severity": host_data["severity"],
                        "error_count": host_data["error_count"],
                        "ticket": ticket.dict(),
                        "activity_log": activity_log,
                        "status": "processed"
                    })

                except Exception as alert_error:
                    logger.error(f"Failed to process alert for {host_data['host']}: {alert_error}")
                    processed_alerts.append({
                        "alert_id": alert_id,
                        "host": host_data["host"],
                        "severity": host_data["severity"],
                        "error_count": host_data["error_count"],
                        "status": "failed",
                        "error": str(alert_error)
                    })

            return {
                "status": "completed",
                "scan_time_range": time_range,
                "total_error_events": len(error_events),
                "affected_hosts": len(affected_hosts),
                "processed_alerts": len([a for a in processed_alerts if a["status"] == "processed"]),
                "failed_alerts": len([a for a in processed_alerts if a["status"] == "failed"]),
                "alerts": processed_alerts
            }

        except Exception as e:
            logger.error(f"Error in scan_and_create_alerts: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "scan_time_range": time_range
            }
