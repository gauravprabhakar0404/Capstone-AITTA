"""
Configuration module for AITTA
Centralized application configuration and settings
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration"""

    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

    # Splunk
    SPLUNK_HOST = os.getenv("SPLUNK_HOST", "")
    SPLUNK_TOKEN = os.getenv("SPLUNK_TOKEN", "")
    SPLUNK_USERNAME = os.getenv("SPLUNK_USERNAME", "")
    SPLUNK_PASSWORD = os.getenv("SPLUNK_PASSWORD", "")

    # Jira
    JIRA_URL = os.getenv("JIRA_URL", "")
    JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "OPS")

    # CMDB
    CMDB_API_URL = os.getenv("CMDB_API_URL", "")
    CMDB_USERNAME = os.getenv("CMDB_USERNAME", "")
    CMDB_PASSWORD = os.getenv("CMDB_PASSWORD", "")

    # Application
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # Agent
    AGENT_LOG_TIMERANGE = int(os.getenv("AGENT_LOG_TIMERANGE", "30"))
    AGENT_MAX_ACTIVITY_LOG = int(os.getenv("AGENT_MAX_ACTIVITY_LOG", "100"))
    AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "60"))

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aitta.db")

    # Security
    API_KEY = os.getenv("API_KEY", "")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Mock mode - individual component control
    MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"  # Global override
    USE_MOCK_SPLUNK = os.getenv("USE_MOCK_SPLUNK", "false").lower() == "true"
    USE_MOCK_JIRA = os.getenv("USE_MOCK_JIRA", "false").lower() == "true"
    USE_MOCK_CMDB = os.getenv("USE_MOCK_CMDB", "true").lower() == "true"


# Global config instance
config = Config()
