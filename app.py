"""
AITTA - Main Application Entry Point
Automated Incident Triage & Ticketing Agent
"""

import uvicorn
import logging

from config.config import Config
from api.api import app  # Import the FastAPI app

# Initialize configuration
config = Config()

# Configure logging early
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("aitta-main")


def run():
    """Run the AITTA FastAPI application using Uvicorn."""
    logger.info(
        "Starting AITTA API server on %s:%s (debug=%s)",
        config.API_HOST,
        config.API_PORT,
        config.API_DEBUG,
    )
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=config.API_DEBUG,  # Enable reload in debug mode
    )


if __name__ == "__main__":
    run()