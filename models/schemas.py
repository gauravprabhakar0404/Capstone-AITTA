"""
API schemas for AITTA
Pydantic models for request/response validation
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime


class AlertData(BaseModel):
    """Input model for alert data"""
    alert_id: str
    severity: str
    message: str
    host: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = {}


class TicketResponse(BaseModel):
    """Response model for ticket creation"""
    ticket_id: str
    priority: str
    summary: str
    description: str
    assigned_to: str
    url: Optional[str] = None
    created_at: datetime
    processing_time: float


class MetricsResponse(BaseModel):
    """Response model for dashboard metrics"""
    total_tickets: int
    ai_generated: int
    human_created: int
    avg_time_to_ticket: float
    false_positive_rate: float
    priority_accuracy: float


class ActivityLogItem(BaseModel):
    """Model for individual activity log items"""
    time: str
    action: str
    detail: str
    status: str


class IncidentPattern(BaseModel):
    """Model for incident patterns"""
    pattern: str
    count: int
    trend: str


class TimelineItem(BaseModel):
    """Model for timeline data points"""
    day: str
    count: int


class TicketSummary(BaseModel):
    """Model for ticket summary in list views"""
    ticket_id: str
    host: str
    priority: str
    summary: str
    assigned_to: str
    created_at: str
    processing_time: float
    status: str


class TicketDetail(BaseModel):
    """Model for detailed ticket view"""
    ticket_id: str
    alert_id: str
    host: str
    severity: str
    priority: str
    summary: str
    description: str
    assigned_to: str
    created_at: str
    processing_time: float
    status: str


class MCPToolsResponse(BaseModel):
    """Response model for MCP tools listing"""
    server: str
    tools: Dict[str, Any]
    mock_mode: bool
