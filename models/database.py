"""
Database models for AITTA
SQLAlchemy models for database persistence
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base

# SQLAlchemy base
Base = declarative_base()


class TicketRecord(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String, unique=True, index=True)
    alert_id = Column(String, index=True)
    host = Column(String, index=True)
    severity = Column(String)
    priority = Column(String)
    summary = Column(String)
    description = Column(Text)
    assigned_to = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    processing_time = Column(Float)
    status = Column(String, default="created")


class MetricRecord(Base):
    """Database model for metrics"""
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, index=True)
    total_tickets = Column(Integer, default=0)
    ai_generated = Column(Integer, default=0)
    avg_time_to_ticket = Column(Float, default=0.0)
    false_positive_rate = Column(Float, default=0.0)
    priority_accuracy = Column(Float, default=0.0)


class AgentActivityRecord(Base):
    """Database model for agent activity"""
    __tablename__ = "agent_activity"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    alert_id = Column(String, index=True)
    action = Column(String)
    detail = Column(Text)
    status = Column(String)
