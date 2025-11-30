"""
API endpoints for AITTA
Contains all FastAPI route handlers and middleware setup
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from config.config import Config
from db.database import get_db
from models.schemas import (
    MetricsResponse, ActivityLogItem, IncidentPattern,
    TimelineItem, TicketSummary, TicketDetail, MCPToolsResponse
)
from services.agent import AITTAgent, mcp_manager
from models.schemas import AlertData
from models.database import AgentActivityRecord, TicketRecord

config = Config()
# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/aitta.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create logs directory
Path("logs").mkdir(exist_ok=True)


# ==================== FastAPI Application ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting AITTA application...")
    yield
    logger.info("Shutting down AITTA application...")
    await mcp_manager.cleanup()

app = FastAPI(
    title="AITTA API",
    version="1.0.0",
    description="Automated Incident Triage & Ticketing Agent",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Security ====================
async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key if configured"""
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AITTA API is running",
        "version": "1.0.0",
        "status": "healthy",
        "mock_mode": config.MOCK_MODE,
        "llm_provider": config.LLM_PROVIDER if config.GEMINI_API_KEY or config.ANTHROPIC_API_KEY else "none"
    }


@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics(
    range: str = "7d",
    db: Session = Depends(get_db)
):
    """Get dashboard metrics from database"""
    try:
        # Calculate date range
        days = int(range.replace('d', '')) if 'd' in range else 7
        start_date = datetime.now() - timedelta(days=days)

        # Query tickets
        tickets = db.query(TicketRecord).filter(TicketRecord.created_at >= start_date).all()

        total_tickets = len(tickets)
        ai_generated = total_tickets  # All are AI generated
        avg_time = sum(t.processing_time for t in tickets) / max(total_tickets, 1) / 60  # Convert to minutes

        # Calculate accuracy (simplified - in production, compare with human validation)
        priority_accuracy = 92.3  # Placeholder - implement validation logic
        false_positive_rate = 4.5  # Placeholder - implement FP detection

        return MetricsResponse(
            total_tickets=total_tickets,
            ai_generated=ai_generated,
            human_created=0,
            avg_time_to_ticket=round(avg_time, 2),
            false_positive_rate=false_positive_rate,
            priority_accuracy=priority_accuracy
        )
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        # Return default metrics if database query fails
        return MetricsResponse(
            total_tickets=0,
            ai_generated=0,
            human_created=0,
            avg_time_to_ticket=0.0,
            false_positive_rate=0.0,
            priority_accuracy=0.0
        )


@app.get("/api/agent-activity", response_model=List[ActivityLogItem])
async def get_agent_activity(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get recent agent activity from database"""
    try:
        activities = db.query(AgentActivityRecord)\
            .order_by(AgentActivityRecord.timestamp.desc())\
            .limit(limit)\
            .all()

        return [
            ActivityLogItem(
                time=activity.timestamp.strftime('%H:%M'),
                action=activity.action,
                detail=activity.detail,
                status=activity.status
            )
            for activity in activities
        ]
    except Exception as e:
        logger.error(f"Error fetching activity: {e}")
        return []


@app.get("/api/incident-patterns", response_model=List[IncidentPattern])
async def get_incident_patterns(
    range: str = "7d",
    db: Session = Depends(get_db)
):
    """Get top incident patterns from database"""
    try:
        days = int(range.replace('d', '')) if 'd' in range else 7
        start_date = datetime.now() - timedelta(days=days)

        # Query tickets and group by summary patterns
        tickets = db.query(TicketRecord).filter(TicketRecord.created_at >= start_date).all()

        # Simple pattern detection (improve with ML in production)
        patterns = {}
        for ticket in tickets:
            # Extract pattern from summary
            if 'memory' in ticket.summary.lower():
                key = 'Memory Leak (Java)'
            elif 'database' in ticket.summary.lower() or 'connection' in ticket.summary.lower():
                key = 'Database Connection Pool'
            elif 'disk' in ticket.summary.lower():
                key = 'Disk Space Critical'
            elif 'timeout' in ticket.summary.lower():
                key = 'API Timeout (Gateway)'
            else:
                key = 'Other Issues'

            patterns[key] = patterns.get(key, 0) + 1

        # Convert to list and sort
        pattern_list = [
            IncidentPattern(
                pattern=k,
                count=v,
                trend='+5%'
            )  # Simplified trend
            for k, v in sorted(patterns.items(), key=lambda x: x[1], reverse=True)
        ]

        return pattern_list[:5]
    except Exception as e:
        logger.error(f"Error fetching patterns: {e}")
        return []


@app.get("/api/ticket-timeline", response_model=List[TimelineItem])
async def get_ticket_timeline(
    range_str: str = "7d",
    db: Session = Depends(get_db)
):
    """Get ticket creation timeline from database"""
    try:
        days = int(range_str.replace('d', '')) if 'd' in range_str else 7
        timeline = []

        for i in range(days):
            date = datetime.now() - timedelta(days=days - 1 - i)
            start_of_day = datetime.combine(date.date(), datetime.min.time())
            end_of_day = datetime.combine(date.date(), datetime.max.time())

            count = db.query(TicketRecord)\
                .filter(TicketRecord.created_at >= start_of_day)\
                .filter(TicketRecord.created_at <= end_of_day)\
                .count()

            timeline.append(TimelineItem(
                day=date.strftime('%a'),
                count=count
            ))

        return timeline

    except Exception as e:
        logger.error(f"Error fetching timeline: {e}")
        return []


@app.post("/api/process-alert")
async def process_alert(
    alert: AlertData,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Process an incoming alert through the agent
    This is the main agentic workflow endpoint
    """
    try:
        logger.info(f"Processing alert: {alert.alert_id}")
        agent = AITTAgent(db,config)
        ticket = await agent.process_alert(alert)

        # Get recent activity for this alert
        activities = db.query(AgentActivityRecord)\
            .filter(AgentActivityRecord.alert_id == alert.alert_id)\
            .order_by(AgentActivityRecord.timestamp.desc())\
            .limit(10)\
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

        return {
            "status": "success",
            "ticket": ticket.dict(),
            "activity_log": activity_log
        }
    except Exception as e:
        logger.error(f"Error processing alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mcp/tools/{server}", response_model=MCPToolsResponse)
async def list_mcp_tools(server: str):
    """List available tools from an MCP server"""
    try:
        session = await mcp_manager.connect(server)
        if session is None:
            return MCPToolsResponse(
                server=server,
                tools={"message": "Mock mode or MCP unavailable"},
                mock_mode=True
            )

        tools = await session.list_tools()
        return MCPToolsResponse(
            server=server,
            tools=tools,
            mock_mode=False
        )
    except Exception as e:
        logger.error(f"Error listing tools for {server}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tickets", response_model=List[TicketSummary])
async def get_tickets(
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    """Get all tickets with pagination"""
    tickets = db.query(TicketRecord)\
        .order_by(TicketRecord.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

    return [
        TicketSummary(
            ticket_id=t.ticket_id,
            host=t.host,
            priority=t.priority,
            summary=t.summary,
            assigned_to=t.assigned_to,
            created_at=t.created_at.isoformat(),
            processing_time=t.processing_time,
            status=t.status
        )
        for t in tickets
    ]


@app.get("/api/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific ticket by ID"""
    ticket = db.query(TicketRecord).filter(TicketRecord.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketDetail(
        ticket_id=ticket.ticket_id,
        alert_id=ticket.alert_id,
        host=ticket.host,
        severity=ticket.severity,
        priority=ticket.priority,
        summary=ticket.summary,
        description=ticket.description,
        assigned_to=ticket.assigned_to,
        created_at=ticket.created_at.isoformat(),
        processing_time=ticket.processing_time,
        status=ticket.status
    )


@app.post("/api/scan-and-alert")
async def scan_and_alert(
    time_range: str = "24h",
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    try:
        agent = AITTAgent(db, config)
        result = await agent.scan_and_create_alerts(time_range)

        if result["status"] == "failed":
            raise HTTPException(status_code=500, detail=result.get("error", "Scan failed"))

        return result

    except Exception as e:
        logger.error(f"Error in scan-and-alert: {e}")
        raise HTTPException(status_code=500, detail=f"Scan and alert failed: {str(e)}")
