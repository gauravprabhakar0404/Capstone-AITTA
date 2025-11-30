"""
Models package for AITTA
Contains database models and API schemas
"""

from .database import Base, TicketRecord, MetricRecord, AgentActivityRecord
from .schemas import (
    AlertData, TicketResponse, MetricsResponse,
    ActivityLogItem, IncidentPattern, TimelineItem,
    TicketSummary, TicketDetail, MCPToolsResponse
)

__all__ = [
    # Database models
    "Base",
    "TicketRecord",
    "MetricRecord",
    "AgentActivityRecord",
    # API schemas
    "AlertData",
    "TicketResponse",
    "MetricsResponse",
    "ActivityLogItem",
    "IncidentPattern",
    "TimelineItem",
    "TicketSummary",
    "TicketDetail",
    "MCPToolsResponse"
]
